"""
RAG Service: Medical Knowledge Extraction, Embedding, Ingestion, and Hybrid Retrieval
Uses PyMuPDF for PDF extraction, ChromaDB for persistent vector storage,
FastEmbed (BAAI/bge-small-en-v1.5) for local 384-dimensional dense vectors, and hybrid search.
"""
import os
import re
import math
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
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection_name = settings.CHROMA_COLLECTION_NAME
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
        self._query_cache: Dict[str, Any] = {}

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
        return self._parse_medical_text(combined_text, filename=os.path.basename(file_path))

    def extract_text_from_txt(self, file_path: str) -> Dict[str, Any]:
        """Extract text and structured metadata from a text file."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self._parse_medical_text(content, filename=os.path.basename(file_path))

    def _parse_medical_text(self, text: str, filename: str) -> Dict[str, Any]:
        """Parse structured headers (TITLE, SOURCE, TOPIC, SECTIONS) from medical text."""
        lines = text.splitlines()
        meta = {
            "title": filename.replace(".pdf", "").replace(".txt", "").replace("_", " ").title(),
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
        return {
            "metadata": meta,
            "raw_text": clean_body
        }

    def chunk_document(
        self,
        text: str,
        metadata: Dict[str, Any],
        chunk_size: int = 500,
        chunk_overlap: int = 80
    ) -> List[Dict[str, Any]]:
        """
        Split document into overlapping chunks with section preservation.
        """
        chunks = []
        sections = re.split(r"(--- .+? ---)", text)
        current_section = "General Overview"

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
                    chunk_id = hashlib.sha256(f"{metadata['title']}_{current_section}_{len(chunks)}_{chunk_text[:30]}".encode()).hexdigest()[:16]
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
                            "section": current_section
                        }
                    })
                    # Overlap: keep the last few words
                    overlap_words = current_chunk_words[-max(1, chunk_overlap // 7):]
                    current_chunk_words = overlap_words
                    current_len = sum(len(w) + 1 for w in overlap_words)

            if current_chunk_words:
                chunk_text = " ".join(current_chunk_words)
                chunk_id = hashlib.sha256(f"{metadata['title']}_{current_section}_{len(chunks)}_{chunk_text[:30]}".encode()).hexdigest()[:16]
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
                        "section": current_section
                    }
                })

        return chunks

    def ingest_file(self, file_path: str) -> int:
        """Ingest a PDF or text file into ChromaDB, preventing duplicates."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            parsed = self.extract_text_from_pdf(file_path)
        elif ext in [".txt", ".md"]:
            parsed = self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        chunks = self.chunk_document(parsed["raw_text"], parsed["metadata"])
        if not chunks:
            return 0

        # Clear query cache when new documents are ingested
        self._query_cache.clear()

        # Delete any existing chunks for this document title to allow clean updates
        try:
            self.collection.delete(where={"title": parsed["metadata"]["title"]})
        except Exception:
            pass

        texts = [c["text"] for c in chunks]
        ids = [c["id"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        embeddings = self.generate_embeddings(texts)

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
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
                        "score": final_score
                    })

        # Sort descending by final relevance score
        matched_passages.sort(key=lambda x: x["score"], reverse=True)
        results = matched_passages[:top_k]
        if not metadata_filter:
            self._query_cache[cache_key] = results
        return results

    def get_status(self) -> Dict[str, Any]:
        """Return collection size and diagnostic status."""
        total_chunks = self.collection.count()
        return {
            "collection_name": self.collection_name,
            "total_chunks": total_chunks,
            "storage_path": self.persist_dir,
            "is_ready": total_chunks > 0
        }


# Singleton instance
rag_service = RAGService()
