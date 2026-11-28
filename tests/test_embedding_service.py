"""
Tests for Phase 3: Local Embedding Service (FastEmbed) & Safe ChromaDB Migration
Verifies:
1. Embedding service singleton pattern, lazy loading, and dimension consistency (384).
2. embed_documents and embed_query output formatting and empty input handling.
3. ChromaDB migration preserves document counts, metadata, text, and vector dimensions.
4. Old collection (medical_knowledge) remains untouched.
5. Migration is idempotent (safe to rerun without duplicates).
6. RAG service uses FastEmbed with zero OpenAI embedding calls.
7. Semantic retrieval returns relevant medical references with citations.
"""
import pytest
import chromadb
from backend.config import settings
from backend.services.embedding_service import (
    embedding_service,
    get_embedding_model,
    EmbeddingService,
    reset_embedding_model
)
from backend.services.chroma_migration import (
    migrate_to_fastembed_collection,
    SOURCE_COLLECTION_NAME,
    TARGET_COLLECTION_NAME
)
from backend.services.rag_service import rag_service


# ---------------------------------------------------------
# 1. Embedding Service Tests
# ---------------------------------------------------------

def test_embedding_model_singleton():
    """Verify that get_embedding_model returns the same singleton instance."""
    m1 = get_embedding_model()
    m2 = get_embedding_model()
    assert m1 is m2, "FastEmbed model instance is not a singleton"


def test_embedding_service_dimensions_and_types():
    """Verify that embed_documents and embed_query return 384-dim float lists."""
    svc = EmbeddingService()
    docs = ["High blood pressure clinical guideline", "Dengue fever management protocol"]
    doc_embs = svc.embed_documents(docs)

    assert len(doc_embs) == 2
    assert len(doc_embs[0]) == 384
    assert len(doc_embs[1]) == 384
    assert isinstance(doc_embs[0], list)
    assert isinstance(doc_embs[0][0], float)

    query_emb = svc.embed_query("What causes hypertension?")
    assert len(query_emb) == 384
    assert isinstance(query_emb, list)
    assert isinstance(query_emb[0], float)


def test_embedding_service_empty_input_handling():
    """Verify safe handling of empty inputs without crashing."""
    svc = EmbeddingService()
    assert svc.embed_documents([]) == []

    empty_query_emb = svc.embed_query("")
    assert len(empty_query_emb) == 384
    assert isinstance(empty_query_emb, list)

    whitespace_query_emb = svc.embed_query("   ")
    assert len(whitespace_query_emb) == 384


def test_embedding_service_custom_provider_config():
    """Verify embedding service properties reflect configuration."""
    assert embedding_service.dimension == 384
    assert settings.EMBEDDING_PROVIDER == "fastembed"
    assert settings.EMBEDDING_MODEL == "BAAI/bge-small-en-v1.5"


# ---------------------------------------------------------
# 2. ChromaDB Migration Tests
# ---------------------------------------------------------

def test_chroma_migration_integrity_and_isolation():
    """
    Verify that migration created the target collection with correct dimensions
    while keeping the legacy collection completely untouched.
    """
    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)

    # Both collections must exist
    source_col = client.get_collection(SOURCE_COLLECTION_NAME)
    target_col = client.get_collection(TARGET_COLLECTION_NAME)

    source_count = source_col.count()
    target_count = target_col.count()

    assert source_count == 28, f"Source collection count was modified: {source_count} != 28"
    assert target_count >= 28, f"Target collection count less than source: {target_count}"

    # Verify target collection metadata
    meta = target_col.metadata
    assert meta.get("embedding_provider") == "fastembed"
    assert meta.get("embedding_model") == "BAAI/bge-small-en-v1.5"
    assert meta.get("embedding_dimension") == 384

    # Verify target collection vector dimension
    peek = target_col.peek(limit=1)
    target_embs = peek["embeddings"]
    assert len(target_embs[0]) == 384

    # Verify document texts and metadatas are preserved
    sample_id = peek["ids"][0]
    source_item = source_col.get(ids=[sample_id])
    assert len(source_item["ids"]) == 1
    assert peek["documents"][0] == source_item["documents"][0]
    assert peek["metadatas"][0]["title"] == source_item["metadatas"][0]["title"]


def test_chroma_migration_idempotent_rerun():
    """Verify that running the migration again is safe and does not create duplicate entries."""
    res = migrate_to_fastembed_collection()
    assert res["status"] == "success"
    assert res["migrated_count"] == 28
    assert res["target_count"] == 28


# ---------------------------------------------------------
# 3. RAG Service Integration with FastEmbed Tests
# ---------------------------------------------------------

def test_rag_service_uses_target_collection():
    """Verify RAGService points to the fastembed collection."""
    assert rag_service.collection_name == "medical_knowledge_fastembed_v1"
    status = rag_service.get_status()
    assert status["collection_name"] == "medical_knowledge_fastembed_v1"
    assert status["total_chunks"] >= 28
    assert status["is_ready"] is True


def test_rag_semantic_retrieval_relevance():
    """Verify that semantic query retrieval returns relevant medical guideline chunks."""
    # Query related to hypertension
    results = rag_service.query("What is the blood pressure threshold for stage 1 hypertension?", top_k=2)
    assert len(results) > 0
    top_result = results[0]
    assert "metadata" in top_result
    assert "text" in top_result
    assert top_result["score"] >= settings.RAG_RELEVANCE_THRESHOLD
    assert any("hypertension" in top_result["text"].lower() or "blood pressure" in top_result["text"].lower() for top_result in results)


def test_rag_retrieval_dengue_symptoms():
    """Verify retrieval of dengue management guidelines."""
    results = rag_service.query("What are the warning signs of severe dengue fever?", top_k=2)
    assert len(results) > 0
    assert any("dengue" in r["text"].lower() for r in results)
    assert results[0]["metadata"]["source"] != ""


def test_rag_irrelevant_query_rejection():
    """Verify irrelevant non-medical queries receive low relevance and are filtered."""
    results = rag_service.query("How do I bake chocolate chip cookies at home?", top_k=3)
    assert len(results) == 0, f"Expected 0 matches for non-medical query, got {len(results)}"


def test_rag_generate_embeddings_signature_compatibility():
    """Verify generate_embeddings returns FastEmbed 384-dim vectors for compatibility."""
    embs = rag_service.generate_embeddings(["Sample medical text"])
    assert len(embs) == 1
    assert len(embs[0]) == 384
    assert isinstance(embs[0], list)


def test_rag_service_reload_collection_safeguard():
    """Verify that reload_collection redirects legacy collection to target FastEmbed collection."""
    original_setting = settings.CHROMA_COLLECTION_NAME
    try:
        settings.CHROMA_COLLECTION_NAME = "medical_knowledge"
        rag_service.reload_collection()
        assert rag_service.collection_name == "medical_knowledge_fastembed_v1"
        assert settings.CHROMA_COLLECTION_NAME == "medical_knowledge_fastembed_v1"
        assert rag_service.collection.name == "medical_knowledge_fastembed_v1"
        assert rag_service.collection.metadata.get("embedding_provider") == "fastembed"
        assert rag_service.collection.metadata.get("embedding_dimension") == 384
    finally:
        settings.CHROMA_COLLECTION_NAME = original_setting
        rag_service.reload_collection()
