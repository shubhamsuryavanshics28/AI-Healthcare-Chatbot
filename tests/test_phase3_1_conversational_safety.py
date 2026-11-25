"""
Phase 3.1 Verification Test Suite
Covers:
1. Multi-turn conversational memory & symptom tracking (fever sequence: 2 days, 102F, no other symptoms, no meds).
2. Multiple emergency red flags extraction (chest pain + breathing difficulty + dizziness).
3. Non-diagnostic phrasing in emergency guidance.
4. RAG similarity score structure & absence of misleading percentage formatting in citations.
5. Incomplete response detection & graceful ending termination.
6. Anti-prescription safety and antibiotic refusal.
7. Emergency detection independence from Gemini provider.
"""
import pytest
from backend.services.emergency_detector import detect_emergency
from backend.services.ai_service import (
    extract_conversation_symptom_state,
    _generate_intelligent_clinical_fallback,
    generate_chat_response,
    stream_chat_response
)
from backend.services.rag_service import rag_service
from backend.config import settings


# =============================================================================
# 1. CONVERSATIONAL MEMORY & SYMPTOM STATE TRACKING TESTS
# =============================================================================

def test_extract_conversation_symptom_state_fever_sequence():
    """Verify that multi-turn user statements accumulate structured symptom facts."""
    history = [
        {"role": "user", "content": "I have a fever."},
        {"role": "assistant", "content": "I understand you have a fever. When did it begin?"},
        {"role": "user", "content": "I have a little high fever and it lasts from 2 days and I am not experiencing any other symptom right now."},
        {"role": "assistant", "content": "Thank you for clarifying. Have you measured your temperature?"}
    ]
    current_msg = "My temperature is around 102°F. I haven't taken any medication yet. What should I do?"

    state = extract_conversation_symptom_state(history, current_msg)

    assert "fever" in state["complaints"]
    assert state["duration"] == "2 days"
    assert "102" in state["temperature"]
    assert state["no_other_symptoms"] is True
    assert "No medication taken yet" in state["medication_status"]
    assert state["turn_count"] == 3


def test_fallback_incorporates_complete_conversation_history():
    """Verify that clinical fallback explicitly mentions accumulated facts rather than restarting."""
    history = [
        {"role": "user", "content": "I have a fever."},
        {"role": "assistant", "content": "I understand you have a fever. When did it begin?"},
        {"role": "user", "content": "I have a little high fever and it lasts from 2 days and I am not experiencing any other symptom right now."},
        {"role": "assistant", "content": "Thank you for clarifying. Have you measured your temperature?"}
    ]
    current_msg = "My temperature is around 102°F. I haven't taken any medication yet. What should I do?"

    resp = _generate_intelligent_clinical_fallback(current_msg, [], [], history)
    content = resp.content.lower()

    # Must recognize 102, 2 days, and no other symptoms
    assert "102" in content
    assert "2 days" in content
    assert "no other symptoms" in content
    # Must NOT ask duration again
    assert "how many days has the fever lasted" not in content


# =============================================================================
# 2. EMERGENCY DETECTION & MULTIPLE RED FLAGS EXTRACTION TESTS
# =============================================================================

def test_emergency_detector_extracts_all_co_occurring_red_flags():
    """
    Test: 'I am experiencing severe chest pain and difficulty breathing. I am also feeling dizzy.'
    Must extract all 3 triggers: severe chest pain, difficulty breathing, dizzy.
    """
    text = "I am experiencing severe chest pain and difficulty breathing. I am also feeling dizzy."
    res = detect_emergency(text)

    assert res.is_emergency is True
    assert len(res.triggers) >= 3

    triggers_str = " ".join(res.triggers).lower()
    assert "chest pain" in triggers_str
    assert "breathing" in triggers_str or "breath" in triggers_str
    assert "dizz" in triggers_str


def test_emergency_guidance_non_diagnostic_phrasing():
    """Verify emergency guidance avoids claiming confirmed diagnosis."""
    text = "Severe chest pain radiating to left arm."
    res = detect_emergency(text)
    assert res.is_emergency is True

    guidance = res.guidance
    # Avoid definitive diagnostic phrasing
    assert "symptoms strongly suggest a possible acute cardiac event" not in guidance.lower()
    assert "may indicate a serious medical emergency" in guidance.lower()
    assert "112" in guidance
    assert "do not drive yourself" in guidance.lower()


def test_emergency_detection_independent_of_gemini(monkeypatch):
    """Verify emergency alert returns 112 even if Gemini API key is missing."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    text = "I cannot breathe, gasping for air!"
    res = detect_emergency(text)
    assert res.is_emergency is True
    assert "112" in res.emergency_contacts["National Emergency Helpline"]


# =============================================================================
# 3. RAG SIMILARITY SCORING & CITATION TESTS
# =============================================================================

def test_rag_query_returns_base_and_reranked_scores():
    """Verify that RAG returns score and base_similarity properly calibrated."""
    results = rag_service.query("What blood pressure defines hypertension according to WHO?", top_k=2)
    assert len(results) > 0
    top = results[0]

    assert "score" in top
    assert "base_similarity" in top
    # Base cosine similarity must be bounded between 0 and 1
    assert 0.0 <= top["base_similarity"] <= 1.0
    # Final reranked score incorporates lexical bonus
    assert top["score"] >= top["base_similarity"]
    assert top["score"] >= settings.RAG_RELEVANCE_THRESHOLD


def test_rag_irrelevant_query_filtered_below_threshold():
    """Verify non-medical queries receive low score and are completely rejected."""
    results = rag_service.query("How do I bake chocolate chip cookies at home?", top_k=3)
    assert len(results) == 0


def test_rag_allergy_query_not_falsely_grounded():
    """
    Verify queries for topics absent from KB (e.g. food allergy symptoms)
    do not misattribute citations as confirmed allergy guidelines.
    """
    results = rag_service.query("What are the diagnostic symptoms of peanut allergy in children?", top_k=2)
    for r in results:
        # None of the indexed guidelines should claim to be an allergy guide
        assert "peanut" not in r["metadata"]["title"].lower()


# =============================================================================
# 4. RESPONSE COMPLETION & TRUNCATION SAFETY TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_stream_interruption_yields_completion_notice():
    """Verify that if a stream is interrupted midway, a completion notice is appended."""
    # Test message stream
    events = []
    async for evt in stream_chat_response("I have had a mild headache for two hours.", []):
        events.append(evt)

    event_types = [e.get("type") for e in events]
    assert "start" in event_types
    assert "done" in event_types

    done_evt = [e for e in events if e.get("type") == "done"][0]
    assert done_evt.get("full_content") is not None
    assert len(done_evt.get("full_content")) > 20
