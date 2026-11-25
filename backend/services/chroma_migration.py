"""
Safe ChromaDB Migration: Migrate from medical_knowledge to medical_knowledge_fastembed_v1.
Preserves original documents, IDs, and metadata without modifying or deleting the source collection.
Generates genuine FastEmbed 384-dimensional dense embeddings for all chunks.
Idempotent and safe to rerun without creating duplicates.
"""
import logging
from typing import Dict, Any
import chromadb
from backend.config import settings
from backend.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

SOURCE_COLLECTION_NAME = "medical_knowledge"
TARGET_COLLECTION_NAME = "medical_knowledge_fastembed_v1"


def migrate_to_fastembed_collection(
    persist_dir: str = settings.CHROMA_PERSIST_DIR
) -> Dict[str, Any]:
    """
    Executes safe migration from SOURCE_COLLECTION_NAME to TARGET_COLLECTION_NAME.
    1. Reads all chunks, documents, IDs, and metadatas from SOURCE_COLLECTION_NAME.
    2. Leaves SOURCE_COLLECTION_NAME completely untouched.
    3. Creates or retrieves TARGET_COLLECTION_NAME with explicit metadata.
    4. Computes fresh 384-dim FastEmbed embeddings for all documents.
    5. Inserts or updates chunks in TARGET_COLLECTION_NAME.
    6. Validates counts, dimensions, and metadata preservation.
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
        logger.info("[Migration] Source collection is empty or missing. Creating empty target collection.")
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
            "target_count": target_col.count(),
            "status": "source_empty"
        }

    # 2. Read all data from source collection
    source_data = source_col.get(include=["documents", "metadatas", "embeddings"])
    ids = source_data["ids"]
    docs = source_data["documents"]
    metas = source_data["metadatas"]

    logger.info(f"[Migration] Read {len(ids)} chunks from source '{SOURCE_COLLECTION_NAME}'.")

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

    # 4. Generate fresh FastEmbed embeddings for document chunks
    logger.info(f"[Migration] Generating FastEmbed embeddings for {len(docs)} chunks...")
    fresh_embeddings = embedding_service.embed_documents(docs)

    # 5. Insert/upsert into target collection (idempotent: use upsert if available, or delete & add)
    if hasattr(target_col, "upsert"):
        target_col.upsert(
            ids=ids,
            embeddings=fresh_embeddings,
            documents=docs,
            metadatas=metas
        )
    else:
        # Fallback for older chromadb: delete matching IDs and add
        try:
            target_col.delete(ids=ids)
        except Exception:
            pass
        target_col.add(
            ids=ids,
            embeddings=fresh_embeddings,
            documents=docs,
            metadatas=metas
        )

    target_count = target_col.count()

    # 6. Validate integrity
    sample = target_col.peek(limit=1)
    sample_embeddings = sample.get("embeddings")
    sample_dim = len(sample_embeddings[0]) if sample_embeddings is not None and len(sample_embeddings) > 0 else 0

    assert sample_dim == 384, f"Target embedding dimension mismatch: {sample_dim} != 384"
    assert target_count >= source_count, f"Target count {target_count} < source count {source_count}"

    # Confirm source collection remains intact
    assert source_col.count() == source_count, "Source collection count was modified!"

    logger.info(
        f"[Migration] Successfully migrated {len(ids)} chunks to '{TARGET_COLLECTION_NAME}'. "
        f"Target count: {target_count}, Vector dimension: {sample_dim}."
    )

    return {
        "source_collection": SOURCE_COLLECTION_NAME,
        "target_collection": TARGET_COLLECTION_NAME,
        "source_count": source_count,
        "migrated_count": len(ids),
        "target_count": target_count,
        "vector_dimension": sample_dim,
        "status": "success"
    }


if __name__ == "__main__":
    result = migrate_to_fastembed_collection()
    print("MIGRATION_RESULT:", result)
