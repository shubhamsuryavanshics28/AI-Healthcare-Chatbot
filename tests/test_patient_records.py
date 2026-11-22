"""
Automated Tests: Patient Profile, Medical Records CRUD, and Per-User Data Isolation
"""
import pytest
from fastapi import status


def test_patient_profile_update_and_get(client, authenticated_patient):
    # Update profile
    update_payload = {
        "gender": "Female",
        "blood_group": "B+",
        "height_cm": 165.5,
        "weight_kg": 62.0,
        "emergency_contact_name": "Jane Doe",
        "emergency_contact_phone": "+91 9988776655",
        "emergency_contact_relation": "Sister",
        "general_notes": "Mild lactose intolerance"
    }
    resp = client.put("/patients/profile", json=update_payload, headers=authenticated_patient["headers"])
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["blood_group"] == "B+"
    assert data["height_cm"] == 165.5

    # Retrieve profile
    get_resp = client.get("/patients/profile", headers=authenticated_patient["headers"])
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["emergency_contact_name"] == "Jane Doe"


def test_medical_conditions_crud(client, authenticated_patient):
    # Create condition
    cond_payload = {
        "condition_name": "Essential Hypertension",
        "diagnosed_date": "2024-03-15",
        "status": "managed",
        "notes": "Controlled with daily exercise and low-sodium DASH diet"
    }
    create_resp = client.post("/patients/medical-history", json=cond_payload, headers=authenticated_patient["headers"])
    assert create_resp.status_code == status.HTTP_201_CREATED
    cond_id = create_resp.json()["id"]

    # Read conditions list
    list_resp = client.get("/patients/medical-history", headers=authenticated_patient["headers"])
    assert list_resp.status_code == status.HTTP_200_OK
    assert any(c["id"] == cond_id for c in list_resp.json())

    # Update condition
    update_payload = {"status": "resolved", "notes": "Discontinued after full normalization"}
    up_resp = client.put(f"/patients/medical-history/{cond_id}", json=update_payload, headers=authenticated_patient["headers"])
    assert up_resp.status_code == status.HTTP_200_OK
    assert up_resp.json()["status"] == "resolved"

    # Delete condition
    del_resp = client.delete(f"/patients/medical-history/{cond_id}", headers=authenticated_patient["headers"])
    assert del_resp.status_code == status.HTTP_200_OK

    # Verify deleted
    list_resp_after = client.get("/patients/medical-history", headers=authenticated_patient["headers"])
    assert not any(c["id"] == cond_id for c in list_resp_after.json())


def test_allergies_crud(client, authenticated_patient):
    allergy_payload = {
        "allergen": "Amoxicillin / Penicillin",
        "reaction": "Generalized urticaria and facial swelling",
        "severity": "severe",
        "notes": "Prescribed cephalosporins as alternative"
    }
    create_resp = client.post("/patients/allergies", json=allergy_payload, headers=authenticated_patient["headers"])
    assert create_resp.status_code == status.HTTP_201_CREATED
    allergy_id = create_resp.json()["id"]

    # List
    list_resp = client.get("/patients/allergies", headers=authenticated_patient["headers"])
    assert any(a["id"] == allergy_id for a in list_resp.json())

    # Delete
    del_resp = client.delete(f"/patients/allergies/{allergy_id}", headers=authenticated_patient["headers"])
    assert del_resp.status_code == status.HTTP_200_OK


def test_patient_medications_crud(client, authenticated_patient):
    med_payload = {
        "medication_name": "Amlodipine Besylate",
        "dosage": "5 mg",
        "frequency": "Once daily at morning",
        "start_date": "2024-01-10",
        "is_current": True,
        "notes": "Prescribed for blood pressure management"
    }
    create_resp = client.post("/patients/medications", json=med_payload, headers=authenticated_patient["headers"])
    assert create_resp.status_code == status.HTTP_201_CREATED
    med_id = create_resp.json()["id"]

    # List
    list_resp = client.get("/patients/medications", headers=authenticated_patient["headers"])
    assert any(m["id"] == med_id for m in list_resp.json())

    # Delete
    del_resp = client.delete(f"/patients/medications/{med_id}", headers=authenticated_patient["headers"])
    assert del_resp.status_code == status.HTTP_200_OK


def test_strict_user_data_isolation(client, authenticated_patient, second_patient):
    """
    CRITICAL SECURITY & PRIVACY REQUIREMENT:
    Ensure Patient B CANNOT access, update, or delete Patient A's health records.
    """
    # Patient A creates a medical condition
    cond_resp = client.post(
        "/patients/medical-history",
        json={"condition_name": "Patient A Chronic Illness", "status": "active"},
        headers=authenticated_patient["headers"]
    )
    patient_a_cond_id = cond_resp.json()["id"]

    # Patient B attempts to update Patient A's condition
    unauthorized_up = client.put(
        f"/patients/medical-history/{patient_a_cond_id}",
        json={"notes": "Hacked by Patient B"},
        headers=second_patient["headers"]
    )
    assert unauthorized_up.status_code == status.HTTP_404_NOT_FOUND

    # Patient B attempts to delete Patient A's condition
    unauthorized_del = client.delete(
        f"/patients/medical-history/{patient_a_cond_id}",
        headers=second_patient["headers"]
    )
    assert unauthorized_del.status_code == status.HTTP_404_NOT_FOUND

    # Patient B lists their conditions and should NOT see Patient A's condition
    patient_b_list = client.get("/patients/medical-history", headers=second_patient["headers"])
    assert not any(c["id"] == patient_a_cond_id for c in patient_b_list.json())
