"""
ArogyaAI System Launcher
Project ID: 26P_3CSE294
Title: AI-Based Healthcare Chatbot for Patient Assistance and Triage
"""
import uvicorn
from backend.config import settings

if __name__ == "__main__":
    print("=" * 70)
    print(f"🚀 Starting {settings.APP_NAME}")
    print(f"📌 Project ID: {settings.PROJECT_ID}")
    print(f"🌐 Server Host: {settings.HOST}:{settings.PORT}")
    print(f"📖 Swagger Docs: http://localhost:{settings.PORT}/docs")
    print(f"🏥 Web Interface: http://localhost:{settings.PORT}/")
    print("=" * 70)

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
