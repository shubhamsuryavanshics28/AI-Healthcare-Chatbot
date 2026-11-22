"""
Application Configuration and Settings
Loaded from environment variables or .env file with safe defaults.
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    APP_NAME: str = "AI Healthcare Chatbot & Patient Triage System"
    PROJECT_ID: str = "26P_3CSE294"

    # Security & JWT
    SECRET_KEY: str = "dev-secret-key-change-in-production-min-32-chars-long-26p-3cse294"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = "sqlite:///./healthcare.db"

    # OpenAI Integration
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_TIMEOUT_SECONDS: float = 30.0

    # ChromaDB & RAG
    CHROMA_PERSIST_DIR: str = "./data/chromadb"
    CHROMA_COLLECTION_NAME: str = "medical_knowledge"
    RAG_TOP_K: int = 3
    RAG_RELEVANCE_THRESHOLD: float = 0.38

    # Emergency Services (India / Localized defaults)
    EMERGENCY_HELPLINE_INDIA: str = "112"
    AMBULANCE_INDIA: str = "102"
    WOMEN_HELPLINE_INDIA: str = "1091"

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
