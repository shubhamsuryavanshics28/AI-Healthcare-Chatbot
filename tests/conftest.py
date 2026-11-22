"""
Pytest Fixtures and Test Environment Setup
Provides clean database sessions and FastAPI TestClient.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from backend.database import Base, get_db
from backend.main import app
from backend.services.medicine_service import seed_medicine_database
from backend.services.rag_service import rag_service

# Use in-memory SQLite database for isolated test execution
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Session-level setup: Ensure tables and seeds exist."""
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    seed_medicine_database(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Provide a fresh, clean database session per test function."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_patient(client):
    """Register and authenticate a primary test patient."""
    register_payload = {
        "email": "patient.test@hospital.org",
        "password": "SecurePassword123!",
        "full_name": "Test Patient",
        "agree_medical_disclaimer": True,
        "agree_privacy_policy": True
    }
    resp = client.post("/auth/register", json=register_payload)
    data = resp.json()
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return {
        "user": data["user"],
        "token": token,
        "headers": headers
    }


@pytest.fixture
def second_patient(client):
    """Register and authenticate a second test patient for data isolation verification."""
    register_payload = {
        "email": "second.patient@hospital.org",
        "password": "SecurePassword123!",
        "full_name": "Second Patient",
        "agree_medical_disclaimer": True,
        "agree_privacy_policy": True
    }
    resp = client.post("/auth/register", json=register_payload)
    data = resp.json()
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return {
        "user": data["user"],
        "token": token,
        "headers": headers
    }
