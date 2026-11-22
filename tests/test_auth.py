"""
Automated Tests: Authentication, Argon2 Hashing, and JWT Authorization
"""
import pytest
from fastapi import status


def test_successful_registration(client):
    payload = {
        "email": "dr.smith@clinic.org",
        "password": "StrongPassword99!",
        "full_name": "Dr. Smith",
        "agree_medical_disclaimer": True,
        "agree_privacy_policy": True
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "dr.smith@clinic.org"
    assert data["user"]["full_name"] == "Dr. Smith"


def test_duplicate_email_registration_fails(client, authenticated_patient):
    # Attempt registering with the already used email
    payload = {
        "email": authenticated_patient["user"]["email"],
        "password": "AnotherPassword123!",
        "full_name": "Duplicate Tester",
        "agree_medical_disclaimer": True,
        "agree_privacy_policy": True
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in response.json()["detail"]


def test_registration_without_disclaimer_consent_fails(client):
    payload = {
        "email": "noconsent@example.com",
        "password": "StrongPassword99!",
        "full_name": "No Consent",
        "agree_medical_disclaimer": False,
        "agree_privacy_policy": True
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "disclaimer" in response.json()["detail"].lower()


def test_successful_login(client, authenticated_patient):
    payload = {
        "email": authenticated_patient["user"]["email"],
        "password": "SecurePassword123!"
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["user"]["id"] == authenticated_patient["user"]["id"]


def test_login_invalid_password(client, authenticated_patient):
    payload = {
        "email": authenticated_patient["user"]["email"],
        "password": "WrongPassword999!"
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid email or password" in response.json()["detail"]


def test_login_nonexistent_user(client):
    payload = {
        "email": "ghost.user@hospital.org",
        "password": "Password123!"
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_profile(client, authenticated_patient):
    response = client.get("/auth/me", headers=authenticated_patient["headers"])
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == authenticated_patient["user"]["id"]
    assert data["email"] == authenticated_patient["user"]["email"]


def test_unauthorized_access_fails(client):
    response = client.get("/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    response = client.get("/auth/me", headers={"Authorization": "Bearer invalid.fake.token"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
