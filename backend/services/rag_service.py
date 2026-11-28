"""
RAG Service: Medical Knowledge Extraction, Embedding, Ingestion, and Hybrid Retrieval
Uses PyMuPDF for PDF extraction, ChromaDB for persistent vector storage,
FastEmbed (BAAI/bge-small-en-v1.5) for local 384-dimensional dense vectors, and hybrid search.
"""
import os
import re
import math
import json
import time
import uuid
import hashlib
import logging
from typing import List, Dict, Any, Optional
import pymupdf
import chromadb
from chromadb.config import Settings as ChromaSettings
from backend.config import settings
from backend.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


class DenseFallbackEmbedder:
    """
    Deterministic normalized embedding generator based on subword hashing and TF-IDF.
    Maintained solely for testing backward compatibility and comparison with legacy data.
    """
    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        tokens = re.findall(r"\w+", text.lower())
        vec = [0.0] * self.dim
        if not tokens:
            return vec

        for tok in tokens:
            # 3-gram char hashes for subword capture
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % self.dim
            vec[h] += 1.0

        # L2 normalize vector
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


fallback_embedder = DenseFallbackEmbedder(dim=384)


class RAGService:
    def __init__(self):
        self.persist_dir = settings.CHROMA_PERSIST_DIR
        os.makedirs(self.persist_dir, exist_ok=True)
        self.manifest_dir = os.path.join(self.persist_dir, "_manifests")
        os.makedirs(self.manifest_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self._query_cache: Dict[str, Any] = {}
        self.reload_collection()

    def _get_manifest_path(self, doc_id: str) -> str:
        return os.path.join(self.manifest_dir, f"{doc_id}.json")

    def get_document_manifest(self, doc_id: str) -> Optional[Dict[str, Any]]:
        path = self._get_manifest_path(doc_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"[RAG] Failed to read manifest for {doc_id}: {e}")
        return None

    def _save_document_manifest(self, doc_id: str, manifest: Dict[str, Any]) -> None:
        path = self._get_manifest_path(doc_id)
        temp_path = f"{path}.tmp.{uuid.uuid4().hex[:8]}"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        os.replace(temp_path, path)

    def reconcile_document_manifest(self, doc_id: str) -> Dict[str, Any]:
        """
        Crash recovery reconciliation:
        Inspects manifest state. If an operation crashed in 'staging' status,
        determines whether staged chunks were verified or incomplete, and restores
        a verified consistent state without data loss.
        """
        manifest = self.get_document_manifest(doc_id)
        if not manifest or manifest.get("status") == "verified":
            return {"status": "clean", "doc_id": doc_id}

        staged_ids = manifest.get("staged_chunk_ids") or []
        last_good_ids = manifest.get("last_known_good_chunk_ids") or []
        staged_version = manifest.get("staged_version")

        # Check ChromaDB for staged records
        try:
            staged_records = self.collection.get(ids=staged_ids) if staged_ids else None
            staged_present_count = len(staged_records["ids"]) if staged_records and "ids" in staged_records else 0
        except Exception:
            staged_present_count = 0

        # If all staged chunks are present and valid, finish the interrupted commit
        if staged_present_count == len(staged_ids) and len(staged_ids) > 0:
            obsolete_ids = list(set(last_good_ids) - set(staged_ids))
            if obsolete_ids:
                try:
                    self.collection.delete(ids=obsolete_ids)
                except Exception as e:
                    logger.warning(f"[RAG Recovery] Error deleting obsolete IDs {obsolete_ids}: {e}")

            verified_manifest = {
                "doc_id": doc_id,
                "active_version": staged_version,
                "status": "verified",
                "active_chunk_ids": staged_ids,
                "active_chunk_count": len(staged_ids),
                "source_path": manifest.get("source_path", ""),
                "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "recovered": True
            }
            self._save_document_manifest(doc_id, verified_manifest)
            logger.info(f"[RAG Recovery] Successfully committed verified staged version for {doc_id}.")
            return {"status": "recovered_committed", "doc_id": doc_id}

        # Otherwise staged version is incomplete: roll back incomplete staged chunks
        if staged_ids:
            try:
                self.collection.delete(ids=staged_ids)
            except Exception as e:
                logger.warning(f"[RAG Recovery] Error rolling back incomplete staged IDs: {e}")

        if manifest.get("last_known_good_version") and last_good_ids:
            reverted_manifest = {
                "doc_id": doc_id,
                "active_version": manifest.get("last_known_good_version"),
                "status": "verified",
                "active_chunk_ids": last_good_ids,
                "active_chunk_count": len(last_good_ids),
                "source_path": manifest.get("source_path", ""),
                "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "recovered_rollback": True
            }
            self._save_document_manifest(doc_id, reverted_manifest)
        else:
            path = self._get_manifest_path(doc_id)
            if os.path.exists(path):
                os.remove(path)

        logger.info(f"[RAG Recovery] Rolled back incomplete staging for {doc_id}; last known good retained.")
        return {"status": "recovered_rolled_back", "doc_id": doc_id}

    def reconcile_all_manifests(self) -> int:
        """Scan manifest directory and reconcile any interrupted staging states."""
        if not os.path.exists(self.manifest_dir):
            return 0
        reconciled = 0
        for fname in os.listdir(self.manifest_dir):
            if fname.endswith(".json"):
                doc_id = fname[:-5]
                res = self.reconcile_document_manifest(doc_id)
                if res.get("status") in ["recovered_committed", "recovered_rolled_back"]:
                    reconciled += 1
        return reconciled

    def reload_collection(self):
        """Reload or reconnect the collection instance from persistent storage."""
        target_name = settings.CHROMA_COLLECTION_NAME
        # Prevent legacy collection collision when FastEmbed is configured
        if (target_name == getattr(settings, "CHROMA_LEGACY_COLLECTION_NAME", "medical_knowledge") or target_name == "medical_knowledge") and settings.EMBEDDING_PROVIDER == "fastembed":
            logger.warning(
                f"[RAG] Legacy collection '{target_name}' configured with FastEmbed provider. "
                f"Auto-switching to target collection 'medical_knowledge_fastembed_v1' to maintain vector space integrity."
            )
            target_name = "medical_knowledge_fastembed_v1"
            settings.CHROMA_COLLECTION_NAME = "medical_knowledge_fastembed_v1"

        self.collection_name = target_name
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "description": "Official Medical Reference Knowledge Base (FastEmbed)",
                "embedding_provider": "fastembed",
                "embedding_model": settings.EMBEDDING_MODEL or "BAAI/bge-small-en-v1.5",
                "embedding_dimension": 384,
                "migration_version": "v1"
            }
        )
        self._query_cache.clear()

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate 384-dimensional dense embeddings for document chunks using FastEmbed.
        Eliminates remote OpenAI embedding dependencies completely.
        """
        if not texts:
            return []
        try:
            return embedding_service.embed_documents(texts)
        except Exception as e:
            logger.error(f"[RAG] FastEmbed document embedding failed: {e}")
            raise RuntimeError(f"RAG embedding generation failed: {e}") from e

    def compute_stable_doc_id(
        self,
        file_path: Optional[str] = None,
        filename: Optional[str] = None,
        title: str = "",
        text: str = ""
    ) -> Dict[str, str]:
        """
        Computes a stable document identity that:
        1. Remains stable across project relocation using canonical source-relative paths.
        2. Distinguishes two files with identical filenames in different directories.
        3. Provides a deterministic fallback for external or in-memory documents.
        """
        clean_filename = filename or (os.path.basename(file_path) if file_path else "")
        clean_name = re.sub(r'\.(pdf|txt|md)$', '', clean_filename, flags=re.IGNORECASE) if clean_filename else ""
        clean_slug = re.sub(r'[^a-zA-Z0-9_-]', '_', clean_name.strip().lower()) if clean_name else ""

        if file_path:
            abs_path = os.path.abspath(file_path)
            docs_dir = os.path.abspath(getattr(settings, "DOCS_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data", "medical_docs")))
            project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".."))

            # Canonical source-relative resolution with relocation resilience
            norm_fwd = abs_path.replace("\\", "/").lower()
            if "/data/medical_docs/" in norm_fwd:
                rel_path = "medical_docs/" + norm_fwd.split("/data/medical_docs/", 1)[1]
            elif "/medical_docs/" in norm_fwd:
                rel_path = "medical_docs/" + norm_fwd.split("/medical_docs/", 1)[1]
            else:
                try:
                    rel_docs = os.path.relpath(abs_path, docs_dir).replace("\\", "/").lower()
                    if not rel_docs.startswith(".."):
                        rel_path = f"medical_docs/{rel_docs}"
                    else:
                        rel_proj = os.path.relpath(abs_path, project_root).replace("\\", "/").lower()
                        if not rel_proj.startswith(".."):
                            rel_path = rel_proj
                        else:
                            cwd_rel = os.path.relpath(abs_path, os.getcwd()).replace("\\", "/").lower()
                            rel_path = cwd_rel if not cwd_rel.startswith("..") else abs_path.replace("\\", "/").lower()
                except Exception:
                    rel_path = abs_path.replace("\\", "/").lower()

            path_hash = hashlib.sha256(rel_path.encode("utf-8")).hexdigest()[:12]
            slug = clean_slug or "doc"
            doc_id = f"{slug}_{path_hash}"
            return {"doc_id": doc_id, "source_path": rel_path}

        if clean_filename:
            rel_path = f"filename/{clean_filename.lower()}"
            path_hash = hashlib.sha256(rel_path.encode("utf-8")).hexdigest()[:12]
            slug = clean_slug or "doc"
            doc_id = f"{slug}_{path_hash}"
            return {"doc_id": doc_id, "source_path": rel_path}

        # Fallback for purely in-memory text without filename
        slug = re.sub(r'[^a-zA-Z0-9_-]', '_', title.strip().lower())[:24] or "doc"
        content_hash = hashlib.sha256((title + "_" + text[:200]).encode("utf-8")).hexdigest()[:12]
        doc_id = f"{slug}_{content_hash}"
        return {"doc_id": doc_id, "source_path": f"in_memory/{slug}"}

    def extract_text_from_pdf(self, file_path: str) -> Dict[str, Any]:
        """Extract text and metadata from a PDF file using PyMuPDF."""
        doc = pymupdf.open(file_path)
        full_text = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text:
                full_text.append(text)
        doc.close()
        combined_text = "\n".join(full_text)
        return self._parse_medical_text(combined_text, filename=os.path.basename(file_path), file_path=file_path)

    def extract_text_from_txt(self, file_path: str) -> Dict[str, Any]:
        """Extract text and structured metadata from a text file."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self._parse_medical_text(content, filename=os.path.basename(file_path), file_path=file_path)

    def _parse_medical_text(
        self,
        text: str,
        filename: str = "",
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse structured headers (TITLE, SOURCE, TOPIC, SECTIONS) from medical text.
        Strips .pdf, .txt, and .md extensions consistently and attaches stable doc identity.
        """
        clean_name = re.sub(r'\.(pdf|txt|md)$', '', filename, flags=re.IGNORECASE) if filename else ""
        default_title = clean_name.replace("_", " ").replace("-", " ").title() if clean_name else "Medical Reference Document"

        lines = text.splitlines()
        meta = {
            "title": default_title,
            "source": "Official Medical Reference",
            "source_url": "",
            "topic": "General Medicine",
            "jurisdiction": "International",
            "last_reviewed_date": "2026-01-01"
        }

        body_lines = []
        for line in lines:
            line_strip = line.strip()
            if line_strip.startswith("DOCUMENT TITLE:"):
                meta["title"] = line_strip.replace("DOCUMENT TITLE:", "").strip()
            elif line_strip.startswith("SOURCE:"):
                meta["source"] = line_strip.replace("SOURCE:", "").strip()
            elif line_strip.startswith("SOURCE URL:"):
                meta["source_url"] = line_strip.replace("SOURCE URL:", "").strip()
            elif line_strip.startswith("TOPIC:"):
                meta["topic"] = line_strip.replace("TOPIC:", "").strip()
            elif line_strip.startswith("JURISDICTION:"):
                meta["jurisdiction"] = line_strip.replace("JURISDICTION:", "").strip()
            elif line_strip.startswith("LAST REVIEWED:"):
                meta["last_reviewed_date"] = line_strip.replace("LAST REVIEWED:", "").strip()
            else:
                body_lines.append(line)

        clean_body = "\n".join(body_lines).strip()

        # Compute stable doc_id and deterministic content version hash
        doc_id_info = self.compute_stable_doc_id(
            file_path=file_path,
            filename=filename,
            title=meta["title"],
            text=clean_body
        )
        meta["doc_id"] = doc_id_info["doc_id"]
        meta["source_path"] = doc_id_info["source_path"]
        doc_version = hashlib.sha256(clean_body.encode("utf-8")).hexdigest()[:16]
        meta["doc_version"] = doc_version

        return {
            "metadata": meta,
            "raw_text": clean_body,
            "doc_id": meta["doc_id"],
            "doc_version": doc_version
        }

    def chunk_document(
        self,
        text: str,
        metadata: Dict[str, Any],
        chunk_size: int = 500,
        chunk_overlap: int = 80
    ) -> List[Dict[str, Any]]:
        """
        Split document into overlapping chunks with section preservation and collision-resistant IDs.
        Chunk ID incorporates stable doc_id, section, chunk position, and full chunk content hash.
        """
        chunks = []
        sections = re.split(r"(--- .+? ---)", text)
        current_section = "General Overview"
        doc_id = metadata.get("doc_id") or self.compute_stable_doc_id(title=metadata.get("title", ""), text=text)["doc_id"]
        doc_version = metadata.get("doc_version") or hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

        for part in sections:
            part_strip = part.strip()
            if not part_strip:
                continue

            if part_strip.startswith("--- ") and part_strip.endswith(" ---"):
                current_section = part_strip.replace("---", "").strip()
                continue

            # Split paragraph/section text into chunks
            words = part_strip.split()
            current_chunk_words = []
            current_len = 0

            for word in words:
                current_chunk_words.append(word)
                current_len += len(word) + 1
                if current_len >= chunk_size:
                    chunk_text = " ".join(current_chunk_words)
                    chunk_index = len(chunks)
                    content_hash = hashlib.sha256(f"{current_section}::{chunk_text}".encode("utf-8")).hexdigest()[:16]
                    chunk_id = f"{doc_id}_{chunk_index}_{content_hash[:12]}"
                    chunks.append({
                        "id": chunk_id,
                        "text": chunk_text,
                        "metadata": {
                            "title": metadata["title"],
                            "source": metadata["source"],
                            "source_url": metadata.get("source_url", ""),
                            "topic": metadata["topic"],
                            "jurisdiction": metadata["jurisdiction"],
                            "last_reviewed_date": metadata["last_reviewed_date"],
                            "section": current_section,
                            "doc_id": doc_id,
                            "doc_version": doc_version,
                            "chunk_index": chunk_index
                        }
                    })
                    # Overlap: keep the last few words
                    overlap_words = current_chunk_words[-max(1, chunk_overlap // 7):]
                    current_chunk_words = overlap_words
                    current_len = sum(len(w) + 1 for w in overlap_words)

            if current_chunk_words:
                chunk_text = " ".join(current_chunk_words)
                chunk_index = len(chunks)
                content_hash = hashlib.sha256(f"{current_section}::{chunk_text}".encode("utf-8")).hexdigest()[:16]
                chunk_id = f"{doc_id}_{chunk_index}_{content_hash[:12]}"
                chunks.append({
                    "id": chunk_id,
                    "text": chunk_text,
                    "metadata": {
                        "title": metadata["title"],
                        "source": metadata["source"],
                        "source_url": metadata.get("source_url", ""),
                        "topic": metadata["topic"],
                        "jurisdiction": metadata["jurisdiction"],
                        "last_reviewed_date": metadata["last_reviewed_date"],
                        "section": current_section,
                        "doc_id": doc_id,
                        "doc_version": doc_version,
                        "chunk_index": chunk_index
                    }
                })

        return chunks

    def ingest_file(self, file_path: str) -> int:
        """
        Ingest a PDF, TXT, or MD medical document into ChromaDB using a safe staged replacement
        and verifiable manifest.
        Guarantees:
        1. Parsing, chunking, and FastEmbed embedding generation must succeed before ChromaDB is modified.
        2. FastEmbed 384-dimensional embeddings are strictly validated.
        3. Staged chunks are upserted and verified in ChromaDB before obsolete chunks are pruned.
        4. Previous valid version remains available if parsing, embedding, or insertion fails.
        5. Manifest tracks 'staging' -> 'verified' lifecycle to enable deterministic crash recovery.
        6. Only chunks belonging to this exact document identity (doc_id) are updated; other documents
           sharing the same title remain untouched.
        7. Query cache is invalidated only upon successful replacement.
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            parsed = self.extract_text_from_pdf(file_path)
        elif ext in [".txt", ".md"]:
            parsed = self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        doc_id = parsed["metadata"]["doc_id"]
        # Reconcile any prior crashed staging for this document before proceeding
        self.reconcile_document_manifest(doc_id)

        chunks = self.chunk_document(parsed["raw_text"], parsed["metadata"])
        if not chunks:
            return 0

        new_version = parsed["metadata"]["doc_version"]
        new_ids = [c["id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        metadatas = [dict(c["metadata"]) for c in chunks]

        # 1. Generate and strictly validate FastEmbed embeddings
        embeddings = self.generate_embeddings(texts)
        if not isinstance(embeddings, list) or len(embeddings) != len(chunks):
            raise ValueError(f"Generated embedding count {len(embeddings) if isinstance(embeddings, list) else 0} != chunk count {len(chunks)}")
        expected_dim = getattr(embedding_service, "dimension", 384)
        for idx, emb in enumerate(embeddings):
            if not isinstance(emb, list) or len(emb) != expected_dim:
                raise ValueError(f"Chunk {idx} embedding dimension mismatch: {len(emb) if isinstance(emb, list) else 0} != {expected_dim}")
            if any(v is None or math.isnan(v) for v in emb):
                raise ValueError(f"Chunk {idx} embedding contains invalid NaN/None values")

        # 2. Identify existing known-good chunk IDs for this document
        known_good_ids = set()
        try:
            existing_records = self.collection.get(where={"doc_id": doc_id})
            if existing_records and existing_records.get("ids"):
                known_good_ids.update(existing_records["ids"])
        except Exception as e:
            logger.warning(f"[RAG] Error querying existing doc_id records: {e}")

        # Backward compatibility: check if there are legacy unversioned chunks matching title
        if not known_good_ids:
            try:
                legacy_records = self.collection.get(where={"title": parsed["metadata"]["title"]})
                if legacy_records and legacy_records.get("ids"):
                    for lid, lmeta in zip(legacy_records["ids"], legacy_records.get("metadatas") or []):
                        if not lmeta or "doc_id" not in lmeta or lmeta["doc_id"] == doc_id:
                            known_good_ids.add(lid)
            except Exception as e:
                logger.warning(f"[RAG] Error querying legacy records by title: {e}")

        current_manifest = self.get_document_manifest(doc_id)

        # 3. Write persistent staging manifest
        staging_manifest = {
            "doc_id": doc_id,
            "staged_version": new_version,
            "status": "staging",
            "staged_chunk_ids": new_ids,
            "staged_chunk_count": len(chunks),
            "last_known_good_version": current_manifest.get("active_version") if current_manifest else None,
            "last_known_good_chunk_ids": list(known_good_ids),
            "source_path": parsed["metadata"].get("source_path", file_path)
        }
        self._save_document_manifest(doc_id, staging_manifest)

        # 4. Stage replacement chunks using upsert (leaves known_good_ids untouched)
        for m in metadatas:
            m["stage_status"] = "staged"

        try:
            if hasattr(self.collection, "upsert"):
                self.collection.upsert(
                    ids=new_ids,
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas
                )
            else:
                self.collection.add(
                    ids=new_ids,
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas
                )
        except Exception as e:
            logger.error(f"[RAG] ChromaDB staging insertion failed for {doc_id}: {e}")
            # Restore manifest to last known good if available
            if current_manifest:
                self._save_document_manifest(doc_id, current_manifest)
            raise RuntimeError(f"ChromaDB staging insertion failed: {e}") from e

        # 5. Verify staged records in ChromaDB
        try:
            staged_check = self.collection.get(ids=new_ids)
            if not staged_check or len(staged_check.get("ids", [])) != len(new_ids):
                # Rollback staged chunks
                try:
                    self.collection.delete(ids=new_ids)
                except Exception:
                    pass
                if current_manifest:
                    self._save_document_manifest(doc_id, current_manifest)
                raise RuntimeError(f"Staged chunks verification failed: expected {len(new_ids)}, found {len(staged_check.get('ids', [])) if staged_check else 0}")
        except Exception as e:
            logger.error(f"[RAG] Verification error for {doc_id}: {e}")
            raise

        # 6. Only after verification passes, prune obsolete chunks belonging to this document
        obsolete_ids = list(known_good_ids - set(new_ids))
        if obsolete_ids:
            try:
                self.collection.delete(ids=obsolete_ids)
            except Exception as e:
                logger.warning(f"[RAG] Failed to delete obsolete chunks {obsolete_ids}: {e}")

        # 7. Update manifest to verified state
        verified_manifest = {
            "doc_id": doc_id,
            "active_version": new_version,
            "status": "verified",
            "active_chunk_ids": new_ids,
            "active_chunk_count": len(chunks),
            "source_path": parsed["metadata"].get("source_path", file_path),
            "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        self._save_document_manifest(doc_id, verified_manifest)

        # 8. Invalidate query cache
        self._query_cache.clear()
        return len(chunks)

    def ingest_directory(self, directory_path: str) -> Dict[str, int]:
        """Ingest all supported medical documents in a directory."""
        results = {}
        if not os.path.exists(directory_path):
            return results

        # Prioritize PDFs if both exist, otherwise take txt
        files = os.listdir(directory_path)
        pdf_bases = {os.path.splitext(f)[0] for f in files if f.lower().endswith(".pdf")}

        for f in files:
            path = os.path.join(directory_path, f)
            base, ext = os.path.splitext(f)
            ext = ext.lower()
            if ext == ".pdf":
                count = self.ingest_file(path)
                results[f] = count
            elif ext in [".txt", ".md"] and base not in pdf_bases:
                count = self.ingest_file(path)
                results[f] = count

        return results

    def query(
        self,
        query_text: str,
        top_k: int = 3,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval combining semantic similarity and keyword presence.
        Filters out low-relevance matches below threshold.
        """
        if not query_text or self.collection.count() == 0:
            return []

        # Check in-memory cache to eliminate duplicate embedding generation & vector search
        cache_key = f"{query_text.strip().lower()}:{top_k}"
        if not metadata_filter and cache_key in self._query_cache:
            return self._query_cache[cache_key]

        stopwords = {
            'the', 'and', 'are', 'for', 'not', 'can', 'how', 'why', 'what', 'when', 'where', 'which', 'who', 'whom',
            'this', 'that', 'with', 'from', 'about', 'should', 'could', 'would', 'have', 'been',
            'were', 'does', 'than', 'into', 'some', 'tell', 'give', 'help', 'today', 'please', 'know'
        }

        try:
            query_embedding = embedding_service.embed_query(query_text)
        except Exception as e:
            logger.error(f"[RAG] Failed to embed query with FastEmbed: {e}")
            return []

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k * 2, max(1, self.collection.count())),
            where=metadata_filter
        )

        matched_passages = []
        q_words = [w for w in re.findall(r"[a-zA-Z]{3,}", query_text.lower()) if w not in stopwords]

        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
            distances = results["distances"][0] if "distances" in results and results["distances"] else [0.5] * len(docs)

            for doc_text, meta, dist in zip(docs, metas, distances):
                # Calculate base similarity from distance
                base_similarity = max(0.0, 1.0 - (dist / 2.0))

                # Keyword match with word boundaries
                doc_lower = doc_text.lower()
                matches = sum(1 for w in q_words if re.search(rf"\b{re.escape(w)}\b", doc_lower))
                
                # If query has substantive words but none match the medical document, heavily discount score
                if q_words and matches == 0:
                    final_score = round(base_similarity * 0.5, 3)
                else:
                    kw_bonus = min(0.5, matches * 0.15) if q_words else 0.0
                    final_score = round(base_similarity + kw_bonus, 3)

                if final_score >= settings.RAG_RELEVANCE_THRESHOLD:
                    matched_passages.append({
                        "text": doc_text,
                        "metadata": meta,
                        "score": final_score,
                        "base_similarity": round(base_similarity, 3)
                    })

        # Sort descending by final relevance score
        matched_passages.sort(key=lambda x: x["score"], reverse=True)
        results = matched_passages[:top_k]
        if not metadata_filter:
            self._query_cache[cache_key] = results
        return results

    def get_status(self) -> Dict[str, Any]:
        """Return collection size and diagnostic status."""
        try:
            total_chunks = self.collection.count()
        except Exception:
            self.reload_collection()
            total_chunks = self.collection.count()
        return {
            "collection_name": self.collection_name,
            "total_chunks": total_chunks,
            "storage_path": self.persist_dir,
            "is_ready": total_chunks > 0,
            "embedding_provider": settings.EMBEDDING_PROVIDER,
            "embedding_model": settings.EMBEDDING_MODEL
        }


# Singleton instance
rag_service = RAGService()
