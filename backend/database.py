"""
Database Setup & Session Management
Uses SQLAlchemy 2.0 ORM with SQLite backend, portable to PostgreSQL.
"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.config import settings

# Engine configuration - check_same_thread is needed only for SQLite
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
    future=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency providing database session lifecycle."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all database tables based on registered models."""
    # Import all models to ensure metadata registration
    import backend.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
