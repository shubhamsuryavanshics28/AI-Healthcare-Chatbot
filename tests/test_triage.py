"""
Automated Tests: 4-Tier Clinical Triage Protocol and Urgency Categorization
"""
from fastapi import status
from backend.services.triage_service import evaluate_triage


def test_triage_tier_emergency():
    res = evaluate_triage(
        primary_symptom="Severe crushing chest pain",
        duration="30 minutes",
        severity=10,
        associated_symptoms="Cold sweat, breathlessness radiating to jaw"
    )
    assert res.urgency_level == "EMERGENCY"
    assert res.emergency_flag is True
    assert "112" in res.guidance or "Immediate" in res.recommended_timeframe


def test_triage_tier_urgent():
    res = evaluate_triage(
        primary_symptom="High fever above 103F with intense shivering and severe abdominal pain",
        duration="18 hours worsening rapidly",
        severity=8,
        associated_symptoms="Inability to keep liquids down"
    )
    assert res.urgency_level == "URGENT"
    assert "Within 4 to 12 hours" in res.recommended_timeframe


def test_triage_tier_routine():
    res = evaluate_triage(
        primary_symptom="Lingering dull lower back ache and joint stiffness",
        duration="3 weeks",
        severity=5,
        associated_symptoms="Mild morning stiffness"
    )
    assert res.urgency_level == "ROUTINE"
    assert "2 to 3 days" in res.recommended_timeframe


def test_triage_tier_self_care():
    res = evaluate_triage(
        primary_symptom="Mild nasal congestion and sneezing",
        duration="2 days",
        severity=2,
        associated_symptoms="None"
    )
    assert res.urgency_level == "SELF_CARE"
    assert "supportive care" in res.guidance.lower()


def test_triage_assessment_api_endpoint(client, authenticated_patient):
    payload = {
        "primary_symptom": "Persistent productive cough with low-grade fever",
        "duration": "4 days",
        "severity": 5,
        "frequency": "constant",
        "body_location": "Chest",
        "associated_symptoms": "Mild fatigue",
        "relevant_history": "Seasonal bronchitis history"
    }
    resp = client.post("/triage/assess", json=payload, headers=authenticated_patient["headers"])
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["primary_symptom"] == payload["primary_symptom"]
    assert "triage_result" in data
    assert data["triage_result"]["urgency_level"] in ["ROUTINE", "URGENT"]

    # Check history endpoint
    hist_resp = client.get("/triage/history", headers=authenticated_patient["headers"])
    assert hist_resp.status_code == status.HTTP_200_OK
    assert len(hist_resp.json()) >= 1
