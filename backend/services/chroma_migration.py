"""
Safe ChromaDB Migration: Migrate from medical_knowledge to medical_knowledge_fastembed_v1.
Preserves original documents, IDs, and metadata without modifying or deleting the source collection.
Maintains a unique 1:1 mapping for every legacy record.
Generates genuine FastEmbed 384-dimensional dense embeddings for all migrated chunks.
Supports resuming partially completed migrations without re-embedding already migrated records.
Idempotent and safe to rerun across application restarts without creating duplicates.
"""
import math
import logging
from typing import Dict, Any, List
import chromadb
from backend.config import settings
from backend.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

SOURCE_COLLECTION_NAME = "medical_knowledge"
TARGET_COLLECTION_NAME = "medical_knowledge_fastembed_v1"


def is_valid_embedding(emb: Any, expected_dim: int = 384) -> bool:
    """
    Validates that an embedding:
    - Is not None
    - Is a list, tuple, or numpy array of length exactly expected_dim
    - Contains only finite numeric values (supports int, float, numpy scalar types)
    - Contains no NaN or infinite values
    """
    if emb is None:
        return False
    if hasattr(emb, "tolist"):
        try:
            emb = emb.tolist()
        except Exception:
            return False
    if not isinstance(emb, (list, tuple)) or len(emb) != expected_dim:
        return False
    for v in emb:
        if v is None:
            return False
        try:
            fv = float(v)
            if not math.isfinite(fv):
                return False
        except (TypeError, ValueError):
            return False
    return True


def check_migration_status(
    persist_dir: str = settings.CHROMA_PERSIST_DIR
) -> Dict[str, Any]:
    """
    Inspects source and target collections to assess migration status.
    Verifies:
    1. Exact 1:1 legacy ID mapping (every source ID must appear exactly once in target).
    2. Exact document content match between source and target records.
    3. Target embeddings exist, have exactly 384 dimensions, and contain finite numbers.
    """
    client = chromadb.PersistentClient(path=persist_dir)

    try:
        source_col = client.get_collection(SOURCE_COLLECTION_NAME)
        source_count = source_col.count()
    except Exception:
        source_col = None
        source_count = 0

    try:
        target_col = client.get_collection(TARGET_COLLECTION_NAME)
        target_count = target_col.count()
    except Exception:
        target_col = None
        target_count = 0

    if not source_col or source_count == 0:
        return {
            "source_count": 0,
            "target_count": target_count,
            "missing_count": 0,
            "is_complete": True,
            "needs_migration": False
        }

    source_data = source_col.get(include=["documents", "metadatas"])
    source_ids = source_data.get("ids") or []
    source_docs = source_data.get("documents") or []
    source_metas = source_data.get("metadatas") or []

    if not target_col or target_count == 0:
        return {
            "source_count": source_count,
            "target_count": 0,
            "missing_count": len(source_ids),
            "is_complete": False,
            "needs_migration": True
        }

    target_data = target_col.get(ids=source_ids, include=["embeddings", "documents", "metadatas"])
    target_ids = target_data.get("ids") or []
    target_docs = target_data.get("documents") or []
    target_metas = target_data.get("metadatas") or []
    target_embs = target_data.get("embeddings")

    invalid_ids = []
    for sid, sdoc, smeta in zip(source_ids, source_docs, source_metas):
        # 1. Check exact 1:1 presence
        id_count = target_ids.count(sid)
        if id_count != 1:
            invalid_ids.append(sid)
            continue

        t_idx = target_ids.index(sid)

        # 2. Check exact document content
        if t_idx >= len(target_docs) or target_docs[t_idx] != sdoc:
            invalid_ids.append(sid)
            continue

        # 3. Check embedding existence, dimension (384), and finite numbers
        if target_embs is None or t_idx >= len(target_embs) or not is_valid_embedding(target_embs[t_idx], 384):
            invalid_ids.append(sid)
            continue

        # 4. Check metadata preservation: all source metadata key-values must match target metadata
        t_meta = target_metas[t_idx] if t_idx < len(target_metas) and target_metas[t_idx] else {}
        s_meta = smeta if smeta else {}
        if any(t_meta.get(k) != v for k, v in s_meta.items()):
            invalid_ids.append(sid)
            continue

    is_complete = len(invalid_ids) == 0

    return {
        "source_count": source_count,
        "target_count": target_count,
        "missing_count": len(invalid_ids),
        "invalid_ids": invalid_ids,
        "is_complete": is_complete,
        "needs_migration": not is_complete
    }


def migrate_to_fastembed_collection(
    persist_dir: str = settings.CHROMA_PERSIST_DIR
) -> Dict[str, Any]:
    """
    Executes safe, resumable migration from SOURCE_COLLECTION_NAME to TARGET_COLLECTION_NAME.
    1. Reads all legacy chunks from SOURCE_COLLECTION_NAME and captures an ID-keyed snapshot.
    2. Leaves SOURCE_COLLECTION_NAME completely untouched.
    3. Maintains unique 1:1 mapping for every legacy record (never mapping by text alone).
    4. Identifies missing or invalid target records (content mismatch, invalid vector, NaN/inf).
    5. Computes fresh FastEmbed 384-dim embeddings only for missing/invalid chunks.
    6. Upserts repaired/missing chunks into TARGET_COLLECTION_NAME.
    7. Validates every source record 1:1 in target collection (content and dimension).
    8. Verifies source collection immutability using ID-keyed comparison.
    """
    client = chromadb.PersistentClient(path=persist_dir)

    # 1. Access source collection
    try:
        source_col = client.get_collection(SOURCE_COLLECTION_NAME)
        source_count = source_col.count()
    except Exception as e:
        logger.warning(f"[Migration] Source collection '{SOURCE_COLLECTION_NAME}' not found: {e}")
        source_count = 0
        source_col = None

    if not source_col or source_count == 0:
        logger.info("[Migration] Source collection is empty or missing. Ensuring empty target collection exists.")
        target_col = client.get_or_create_collection(
            name=TARGET_COLLECTION_NAME,
            metadata={
                "description": "Official Medical Reference Knowledge Base (FastEmbed)",
                "embedding_provider": "fastembed",
                "embedding_model": settings.EMBEDDING_MODEL or "BAAI/bge-small-en-v1.5",
                "embedding_dimension": 384,
                "migration_version": "v1"
            }
        )
        return {
            "source_collection": SOURCE_COLLECTION_NAME,
            "target_collection": TARGET_COLLECTION_NAME,
            "source_count": 0,
            "migrated_count": 0,
            "newly_embedded_count": 0,
            "target_count": target_col.count(),
            "status": "source_empty"
        }

    # 2. Read all data from source collection and take ID-keyed snapshot
    source_data = source_col.get(include=["documents", "metadatas"])
    source_ids = source_data["ids"]
    source_docs = source_data["documents"]
    source_metas = source_data["metadatas"]
    source_snapshot = {
        sid: (sdoc, dict(smeta) if smeta else {})
        for sid, sdoc, smeta in zip(source_ids, source_docs, source_metas)
    }

    logger.info(f"[Migration] Read {len(source_ids)} chunks from source '{SOURCE_COLLECTION_NAME}'.")

    # 3. Create or access target collection
    target_col = client.get_or_create_collection(
        name=TARGET_COLLECTION_NAME,
        metadata={
            "description": "Official Medical Reference Knowledge Base (FastEmbed)",
            "embedding_provider": "fastembed",
            "embedding_model": settings.EMBEDDING_MODEL or "BAAI/bge-small-en-v1.5",
            "embedding_dimension": 384,
            "migration_version": "v1"
        }
    )

    # 4. Determine missing or invalid legacy records for 1:1 mapping
    target_existing = target_col.get(ids=source_ids, include=["embeddings", "documents", "metadatas"])
    target_ids = target_existing.get("ids") or []
    target_docs = target_existing.get("documents") or []
    target_metas = target_existing.get("metadatas") or []
    target_embs = target_existing.get("embeddings")

    missing_indices = []
    for idx, (sid, sdoc, smeta) in enumerate(zip(source_ids, source_docs, source_metas)):
        # 1. Check exact 1:1 ID presence
        if target_ids.count(sid) != 1:
            missing_indices.append(idx)
            continue

        t_pos = target_ids.index(sid)

        # 2. Check exact document content
        if t_pos >= len(target_docs) or target_docs[t_pos] != sdoc:
            missing_indices.append(idx)
            continue

        # 3. Check embedding existence, dimension (384), and finite numbers
        if target_embs is None or t_pos >= len(target_embs) or not is_valid_embedding(target_embs[t_pos], 384):
            missing_indices.append(idx)
            continue

        # 4. Check metadata preservation: all original metadata keys must be present and match
        t_meta = target_metas[t_pos] if t_pos < len(target_metas) and target_metas[t_pos] else {}
        s_meta = smeta if smeta else {}
        if any(t_meta.get(k) != v for k, v in s_meta.items()):
            missing_indices.append(idx)
            continue

    def _verify_source_immutability():
        current_count = source_col.count()
        if current_count != source_count:
            raise RuntimeError(
                f"[Migration Safety] Source collection count altered! Expected {source_count}, found {current_count}"
            )
        after_data = source_col.get(include=["documents", "metadatas"])
        after_snapshot = {
            sid: (adoc, dict(ameta) if ameta else {})
            for sid, adoc, ameta in zip(after_data["ids"], after_data["documents"], after_data["metadatas"])
        }
        if set(after_snapshot.keys()) != set(source_snapshot.keys()):
            raise RuntimeError("[Migration Safety] Source collection record IDs were altered!")
        for sid, (orig_doc, orig_meta) in source_snapshot.items():
            curr_doc, curr_meta = after_snapshot[sid]
            if curr_doc != orig_doc:
                raise RuntimeError(f"[Migration Safety] Source document content altered for {sid}!")
            if curr_meta != orig_meta:
                raise RuntimeError(f"[Migration Safety] Source metadata altered for {sid}!")

    # 5. If all source records are already mapped and valid, verify source immutability and return up-to-date
    if not missing_indices:
        _verify_source_immutability()
        logger.info(f"[Migration] All {len(source_ids)} source chunks verified valid in '{TARGET_COLLECTION_NAME}'.")
        return {
            "source_collection": SOURCE_COLLECTION_NAME,
            "target_collection": TARGET_COLLECTION_NAME,
            "source_count": source_count,
            "migrated_count": len(source_ids),
            "newly_embedded_count": 0,
            "target_count": target_col.count(),
            "vector_dimension": 384,
            "status": "success",
            "resumed": True
        }

    logger.info(f"[Migration] Resuming migration: {len(missing_indices)} chunks require FastEmbed repair/embedding...")

    # 6. Generate fresh FastEmbed embeddings ONLY for missing/invalid chunks
    missing_ids = [source_ids[i] for i in missing_indices]
    missing_docs = [source_docs[i] for i in missing_indices]
    missing_metas = []
    for i in missing_indices:
        m = dict(source_metas[i]) if source_metas[i] else {}
        m["legacy_chunk_id"] = source_ids[i]
        m["migration_source"] = SOURCE_COLLECTION_NAME
        missing_metas.append(m)

    fresh_embeddings = embedding_service.embed_documents(missing_docs)

    # Validate fresh embeddings before writing
    for idx, (mid, emb) in enumerate(zip(missing_ids, fresh_embeddings)):
        if not is_valid_embedding(emb, 384):
            raise RuntimeError(f"[Migration] Generated embedding for chunk {mid} is invalid or non-finite!")

    # 7. Upsert into target collection
    if hasattr(target_col, "upsert"):
        target_col.upsert(
            ids=missing_ids,
            embeddings=fresh_embeddings,
            documents=missing_docs,
            metadatas=missing_metas
        )
    else:
        try:
            target_col.delete(ids=missing_ids)
        except Exception:
            pass
        target_col.add(
            ids=missing_ids,
            embeddings=fresh_embeddings,
            documents=missing_docs,
            metadatas=missing_metas
        )

    # 8. Post-migration 1:1 validation with explicit exceptions
    final_check = target_col.get(ids=source_ids, include=["embeddings", "documents", "metadatas"])
    final_ids = final_check.get("ids") or []
    final_docs = final_check.get("documents") or []
    final_metas = final_check.get("metadatas") or []
    final_embs = final_check.get("embeddings")

    if len(final_ids) != len(source_ids):
        raise RuntimeError(
            f"[Migration Verification Failed] Expected {len(source_ids)} chunks in target, found {len(final_ids)}"
        )

    for sid, sdoc, smeta in zip(source_ids, source_docs, source_metas):
        if final_ids.count(sid) != 1:
            raise RuntimeError(f"[Migration Verification Failed] Source chunk {sid} not uniquely present in target!")
        t_pos = final_ids.index(sid)
        if final_docs[t_pos] != sdoc:
            raise RuntimeError(f"[Migration Verification Failed] Document content mismatch for {sid}!")
        if final_embs is None or t_pos >= len(final_embs) or not is_valid_embedding(final_embs[t_pos], 384):
            raise RuntimeError(f"[Migration Verification Failed] Invalid embedding vector for {sid}!")
        t_meta = final_metas[t_pos] if t_pos < len(final_metas) and final_metas[t_pos] else {}
        s_meta = smeta if smeta else {}
        if any(t_meta.get(k) != v for k, v in s_meta.items()):
            raise RuntimeError(f"[Migration Verification Failed] Metadata preservation mismatch for {sid}!")

    # Confirm source collection remains 100% intact
    _verify_source_immutability()

    target_count = target_col.count()
    logger.info(
        f"[Migration] Successfully verified {len(source_ids)} chunks in '{TARGET_COLLECTION_NAME}' (repaired/embedded: {len(missing_indices)}). "
        f"Total target count: {target_count}, Vector dimension: 384."
    )

    return {
        "source_collection": SOURCE_COLLECTION_NAME,
        "target_collection": TARGET_COLLECTION_NAME,
        "source_count": source_count,
        "migrated_count": len(source_ids),
        "newly_embedded_count": len(missing_indices),
        "target_count": target_count,
        "vector_dimension": 384,
        "status": "success"
    }


if __name__ == "__main__":
    result = migrate_to_fastembed_collection()
    print("MIGRATION_RESULT:", result)
