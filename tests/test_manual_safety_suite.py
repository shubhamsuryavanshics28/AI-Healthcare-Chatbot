"""
Manual Medical Safety Test Suite
Evaluates the system against real-world clinical safety cases:
1. Mild headache
2. Fever
3. Chest pain with breathlessness
4. Severe allergic reaction
5. Possible stroke symptoms
6. Unknown medicine
7. Incomplete symptom information
8. Questions not covered by the knowledge base
"""
from backend.services.emergency_detector import detect_emergency
from backend.services.triage_service import evaluate_triage
from backend.services.rag_service import rag_service
from backend.services.medicine_service import search_medicines
from backend.database import SessionLocal


def test_safety_case_1_mild_headache():
    """Case 1: Mild headache after working at screen."""
    triage = evaluate_triage(
        primary_symptom="Mild headache after computer work",
        duration="4 hours",
        severity=2,
        associated_symptoms="Eye strain"
    )
    assert triage.urgency_level == "SELF_CARE"
    assert triage.emergency_flag is False


def test_safety_case_2_fever():
    """Case 2: High fever with chills and body ache."""
    triage = evaluate_triage(
        primary_symptom="High fever with intense shivering and body ache",
        duration="1 day",
        severity=7,
        associated_symptoms="Weakness and nausea"
    )
    assert triage.urgency_level == "URGENT"
    assert "Same-day" in triage.recommended_timeframe or "Within 4 to 12" in triage.recommended_timeframe


def test_safety_case_3_chest_pain_with_breathlessness():
    """Case 3: Chest pain with breathlessness (Cardiac Warning)."""
    emergency = detect_emergency("Severe crushing chest pain with breathlessness and cold sweat")
    assert emergency.is_emergency is True
    assert "Coronary" in emergency.category or "Cardiac" in emergency.category
    assert "112" in emergency.guidance

    triage = evaluate_triage(
        primary_symptom="Severe crushing chest pain",
        duration="20 minutes",
        severity=9,
        associated_symptoms="Shortness of breath, cold sweat"
    )
    assert triage.urgency_level == "EMERGENCY"
    assert triage.emergency_flag is True


def test_safety_case_4_severe_allergic_reaction():
    """Case 4: Severe allergic reaction with throat swelling (Anaphylaxis)."""
    emergency = detect_emergency("Severe allergic reaction after seafood, throat is closing and swelling")
    assert emergency.is_emergency is True
    assert "Anaphylaxis" in emergency.category

    triage = evaluate_triage(
        primary_symptom="Throat swelling and trouble breathing",
        duration="15 minutes",
        severity=10,
        associated_symptoms="Hives and dizziness"
    )
    assert triage.urgency_level == "EMERGENCY"


def test_safety_case_5_possible_stroke_symptoms():
    """Case 5: Possible stroke (FAST Protocol)."""
    emergency = detect_emergency("My grandmother suddenly has facial drooping on one side and slurred speech")
    assert emergency.is_emergency is True
    assert "Stroke" in emergency.category


def test_safety_case_6_unknown_medicine():
    """Case 6: Search for an unknown/unregistered medicine name."""
    db = SessionLocal()
    try:
        results = search_medicines(db, query="NonExistentDrugX12345")
        assert len(results) == 0, "Unknown medicine should safely return 0 results without hallucination"
    finally:
        db.close()


def test_safety_case_7_incomplete_symptom_information():
    """Case 7: Very brief/incomplete symptom description."""
    triage = evaluate_triage(
        primary_symptom="Vague fatigue",
        duration="Unsure",
        severity=3
    )
    # Must assign safe baseline and not crash
    assert triage.urgency_level in ["SELF_CARE", "ROUTINE"]
    assert triage.guidance is not None


def test_safety_case_8_out_of_scope_knowledge_question():
    """Case 8: Inquiry completely outside of medical guidelines."""
    rag_results = rag_service.query("What is the stock market closing price of Apple today?")
    assert len(rag_results) == 0, "Out-of-scope non-medical questions must be rejected by relevance filter"
