"""
Automated Tests: RAG Ingestion Pipeline, PyMuPDF Extraction, and ChromaDB Hybrid Retrieval
"""
import os
from fastapi import status
from backend.services.rag_service import rag_service

DATA_DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "medical_docs")


def test_rag_pdf_extraction_and_chunking():
    pdf_path = os.path.join(DATA_DOCS_DIR, "mohfw_india_dengue_guidelines.pdf")
    assert os.path.exists(pdf_path), "Reference PDF should exist"

    extracted = rag_service.extract_text_from_pdf(pdf_path)
    assert "metadata" in extracted
    assert "Dengue" in extracted["metadata"]["title"] or "Dengue" in extracted["raw_text"]

    chunks = rag_service.chunk_document(extracted["raw_text"], extracted["metadata"])
    assert len(chunks) >= 3
    assert all("text" in c and "metadata" in c for c in chunks)


def test_rag_query_retrieval_relevance():
    """Verify semantic retrieval returns relevant documents for clinical inquiries."""
    results = rag_service.query("What medications are contraindicated in dengue fever?", top_k=3)
    assert len(results) > 0
    top_result = results[0]
    assert "Dengue" in top_result["metadata"]["title"]
    assert top_result["score"] >= 0.38


def test_rag_query_rejection_of_irrelevant_topics():
    """Verify system rejects out-of-scope, non-medical queries."""
    results = rag_service.query("How do I bake chocolate chip cookies at home?", top_k=3)
    assert len(results) == 0, "Non-medical queries should be rejected by relevance threshold"


def test_knowledge_status_endpoint(client, authenticated_patient):
    resp = client.get("/knowledge/status", headers=authenticated_patient["headers"])
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["is_ready"] is True
    assert data["total_chunks"] > 0
    assert "available_source_files" in data
