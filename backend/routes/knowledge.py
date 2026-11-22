"""
RAG Knowledge Base Status and Ingestion Routes
"""
import os
from fastapi import APIRouter, Depends, HTTPException, status
from backend.security.auth import get_current_user
from backend.models.user import User
from backend.services.rag_service import rag_service

router = APIRouter(prefix="/knowledge", tags=["RAG Medical Knowledge"])

DATA_DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "medical_docs")


@router.get("/status")
def get_rag_status(current_user: User = Depends(get_current_user)):
    """Return RAG collection statistics and health."""
    status_info = rag_service.get_status()
    available_files = []
    if os.path.exists(DATA_DOCS_DIR):
        available_files = [f for f in os.listdir(DATA_DOCS_DIR) if f.endswith((".pdf", ".txt", ".md"))]

    return {
        **status_info,
        "available_source_files": available_files
    }


@router.post("/ingest")
def trigger_ingestion(current_user: User = Depends(get_current_user)):
    """
    Ingest or re-index official medical documents into persistent ChromaDB.
    """
    if not os.path.exists(DATA_DOCS_DIR):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medical documents directory not found at {DATA_DOCS_DIR}"
        )

    results = rag_service.ingest_directory(DATA_DOCS_DIR)
    total_chunks = sum(results.values())

    return {
        "message": f"Successfully ingested {len(results)} medical documents into ChromaDB.",
        "documents_processed": results,
        "total_chunks_indexed": total_chunks,
        "collection_total": rag_service.collection.count()
    }
