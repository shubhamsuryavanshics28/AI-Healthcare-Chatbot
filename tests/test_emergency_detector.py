"""
Automated Tests: Independent Emergency Safety Detection Engine
Verifies deterministic clinical heuristics, negation handling, and emergency escalation.
"""
from backend.services.emergency_detector import detect_emergency


def test_cardiac_emergency_detection():
    text = "I am experiencing severe chest pain radiating to my left arm with cold sweat."
    res = detect_emergency(text)
    assert res.is_emergency is True
    assert "Coronary" in res.category or "Cardiac" in res.category
    assert res.urgency_code == "EMERGENCY"
    assert "112" in res.guidance


def test_respiratory_distress_detection():
    text = "Patient cannot breathe, is gasping for air, and has blue lips."
    res = detect_emergency(text)
    assert res.is_emergency is True
    assert "Respiratory" in res.category


def test_stroke_fast_protocol_detection():
    text = "Suddenly having slurred speech and facial drooping on one side."
    res = detect_emergency(text)
    assert res.is_emergency is True
    assert "Stroke" in res.category
    assert "FAST" in res.guidance or "112" in res.guidance


def test_anaphylaxis_detection():
    text = "Ate peanuts and having severe allergic reaction, throat is swelling and closing."
    res = detect_emergency(text)
    assert res.is_emergency is True
    assert "Anaphylaxis" in res.category


def test_massive_hemorrhage_detection():
    text = "Accident at home with spurting blood from wound that won't stop."
    res = detect_emergency(text)
    assert res.is_emergency is True
    assert "Bleeding" in res.category or "Trauma" in res.category


def test_negation_handling_prevents_false_positive():
    text = "I have a mild cough and runny nose. I have no chest pain and no difficulty breathing."
    res = detect_emergency(text)
    assert res.is_emergency is False
    assert res.urgency_code == "NON_EMERGENCY"


def test_mild_non_emergency_symptoms():
    text = "Mild headache after working on the computer all day, no other complaints."
    res = detect_emergency(text)
    assert res.is_emergency is False


def test_high_severity_escalation():
    # Severity 10 with pain
    text = "Extreme unbearable abdominal pain, came on suddenly."
    res = detect_emergency(text, severity=10)
    assert res.is_emergency is True
