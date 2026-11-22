"""
API Routers Package
"""
from backend.routes.auth import router as auth_router
from backend.routes.patients import router as patients_router
from backend.routes.chat import router as chat_router
from backend.routes.triage import router as triage_router
from backend.routes.medications import router as medications_router
from backend.routes.knowledge import router as knowledge_router

__all__ = [
    "auth_router",
    "patients_router",
    "chat_router",
    "triage_router",
    "medications_router",
    "knowledge_router"
]
