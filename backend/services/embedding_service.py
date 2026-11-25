"""
Local Embedding Service: FastEmbed Singleton Wrapper.
Provides deterministic, fast, ONNX-accelerated 384-dimensional vector embeddings
for ArogyaAI RAG pipeline using BAAI/bge-small-en-v1.5.
Eliminates all remote API dependencies (e.g. OpenAI) for vector embeddings.
"""
import logging
from typing import List, Optional
from fastembed import TextEmbedding
from backend.config import settings

logger = logging.getLogger(__name__)

# Singleton model instance cache
_embedding_model_instance: Optional[TextEmbedding] = None


def get_embedding_model() -> TextEmbedding:
    """
    Returns the singleton TextEmbedding instance.
    Loads lazily on first access to conserve startup memory.
    """
    global _embedding_model_instance
    if _embedding_model_instance is None:
        model_name = settings.EMBEDDING_MODEL or "BAAI/bge-small-en-v1.5"
        logger.info(f"[Embedding Service] Initializing FastEmbed model: {model_name}")
        try:
            _embedding_model_instance = TextEmbedding(model_name=model_name)
            logger.info(f"[Embedding Service] FastEmbed model '{model_name}' successfully loaded.")
        except Exception as e:
            logger.error(f"[Embedding Service] Failed to load FastEmbed model '{model_name}': {type(e).__name__} - {e}")
            raise RuntimeError(f"Could not initialize FastEmbed model '{model_name}': {e}") from e
    return _embedding_model_instance


def reset_embedding_model():
    """Testing helper to clear singleton cache for isolation."""
    global _embedding_model_instance
    _embedding_model_instance = None


class EmbeddingService:
    """
    Unified local embedding interface for document passages and user search queries.
    Enforces consistent 384-dimensional dense vectors and data formats expected by ChromaDB.
    """
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL or "BAAI/bge-small-en-v1.5"
        self.dimension = 384

    def _get_model(self) -> TextEmbedding:
        return get_embedding_model()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generates 384-dimensional dense embeddings for a list of document chunks.
        FastEmbed applies appropriate passage prefixes/tokenization for BGE models.
        """
        if not texts:
            return []

        # Sanitize empty strings to a space so FastEmbed does not fail
        sanitized_texts = [t if t and t.strip() else " " for t in texts]

        try:
            model = self._get_model()
            # passage_embed yields numpy float32 arrays
            embeddings_gen = model.passage_embed(sanitized_texts)
            embeddings = [emb.tolist() for emb in embeddings_gen]
            return embeddings
        except Exception as e:
            logger.error(f"[Embedding Service] Failed to embed documents: {type(e).__name__} - {e}")
            raise RuntimeError(f"FastEmbed document embedding failed: {e}") from e

    def embed_query(self, text: str) -> List[float]:
        """
        Generates a single 384-dimensional dense embedding for a search query.
        FastEmbed applies query instruction/prefixes for BGE models.
        """
        sanitized_text = text.strip() if text else " "
        try:
            model = self._get_model()
            # query_embed yields numpy float32 array(s)
            embeddings_gen = model.query_embed(sanitized_text)
            embeddings = [emb.tolist() for emb in embeddings_gen]
            if not embeddings:
                return [0.0] * self.dimension
            return embeddings[0]
        except Exception as e:
            logger.error(f"[Embedding Service] Failed to embed query: {type(e).__name__} - {e}")
            raise RuntimeError(f"FastEmbed query embedding failed: {e}") from e


# Singleton service instance
embedding_service = EmbeddingService()
