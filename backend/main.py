"""
Main FastAPI Application Entrypoint
AI Healthcare Chatbot & Patient Triage System
Project ID: 26P_3CSE294
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.database import init_db, SessionLocal
from backend.services.medicine_service import seed_medicine_database
from backend.services.rag_service import rag_service
from backend.routes import (
    auth_router,
    patients_router,
    chat_router,
    triage_router,
    medications_router,
    knowledge_router
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "medical_docs")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    # 1. Initialize SQLite tables
    print("[Startup] Initializing database tables...")
    init_db()

    # 2. Seed curated medicines
    print("[Startup] Seeding medicine repository...")
    db = SessionLocal()
    try:
        med_count = seed_medicine_database(db)
        print(f"[Startup] Medicine repository verified ({med_count} items).")
    finally:
        db.close()

    # 3. Verify / Ingest RAG documents
    if settings.EMBEDDING_PROVIDER == "fastembed" and (
        settings.CHROMA_COLLECTION_NAME == "medical_knowledge"
        or settings.CHROMA_COLLECTION_NAME == getattr(settings, "CHROMA_LEGACY_COLLECTION_NAME", "medical_knowledge")
    ):
        settings.CHROMA_COLLECTION_NAME = "medical_knowledge_fastembed_v1"
        rag_service.collection_name = "medical_knowledge_fastembed_v1"
        rag_service.reload_collection()

    from backend.services.chroma_migration import check_migration_status, migrate_to_fastembed_collection
    mig_status = check_migration_status()
    if mig_status.get("needs_migration"):
        print(f"[Startup] Legacy migration needed ({mig_status.get('missing_count')} chunks missing). Resuming migration...")
        mig_res = migrate_to_fastembed_collection()
        rag_service.reload_collection()
        if mig_res.get("migrated_count", 0) > 0:
            print(f"[Startup] Migrated {mig_res['migrated_count']} chunks to FastEmbed collection.")

    # Reconcile any prior crashed staging operations
    reconciled_count = rag_service.reconcile_all_manifests()
    if reconciled_count > 0:
        print(f"[Startup] Reconciled {reconciled_count} interrupted document staging operations.")

    rag_status = rag_service.get_status()
    if rag_status["total_chunks"] == 0 and os.path.exists(DOCS_DIR):
        print(f"[Startup] Ingesting medical reference documents from disk ({DOCS_DIR}) via FastEmbed...")
        ingest_res = rag_service.ingest_directory(DOCS_DIR)
        rag_service.reload_collection()
        rag_status = rag_service.get_status()
        print(f"[Startup] Ingested {len(ingest_res)} documents into ChromaDB.")

    print(f"[Startup] ChromaDB collection verified ({rag_status['total_chunks']} chunks in {rag_status['collection_name']}).")

    yield

    print("[Shutdown] Application stopping cleanly.")


app = FastAPI(
    title=settings.APP_NAME,
    description="University Major Project: AI-Based Healthcare Chatbot for Patient Assistance and Triage (ID: 26P_3CSE294)",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers at both root and /api for client flexibility
for r in [auth_router, patients_router, chat_router, triage_router, medications_router, knowledge_router]:
    app.include_router(r)
    app.include_router(r, prefix="/api")


# Frontend Static and Page Routes
if os.path.exists(FRONTEND_DIR):
    # Mount frontend static assets
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    # Clean HTML Page Routes
    @app.get("/", response_class=FileResponse)
    def serve_landing():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/login", response_class=FileResponse)
    def serve_login():
        return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))

    @app.get("/register", response_class=FileResponse)
    def serve_register():
        return FileResponse(os.path.join(FRONTEND_DIR, "register.html"))

    @app.get("/dashboard", response_class=FileResponse)
    def serve_dashboard():
        return FileResponse(os.path.join(FRONTEND_DIR, "dashboard.html"))

    @app.get("/chat", response_class=FileResponse)
    def serve_chat():
        return FileResponse(os.path.join(FRONTEND_DIR, "chat.html"))

    @app.get("/profile", response_class=FileResponse)
    def serve_profile():
        return FileResponse(os.path.join(FRONTEND_DIR, "profile.html"))

    @app.get("/history", response_class=FileResponse)
    def serve_history():
        return FileResponse(os.path.join(FRONTEND_DIR, "history.html"))

    @app.get("/medications-page", response_class=FileResponse)
    def serve_medications_page():
        return FileResponse(os.path.join(FRONTEND_DIR, "medications.html"))

    @app.get("/triage", response_class=FileResponse)
    def serve_triage():
        return FileResponse(os.path.join(FRONTEND_DIR, "triage.html"))

    @app.get("/medicine", response_class=FileResponse)
    def serve_medicine():
        return FileResponse(os.path.join(FRONTEND_DIR, "medicine.html"))


@app.get("/health")
def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "project_id": settings.PROJECT_ID,
        "database": "connected",
        "rag_ready": rag_service.get_status()["is_ready"]
    }
