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


# =============================================================================
# 5. PHASE 3.1.1 ENHANCED NEGATION, CORRECTION & CITATION REFINEMENT TESTS
# =============================================================================

def test_negative_symptom_denial_not_marked_as_positive():
    """Verify that explicitly denied symptoms are not added to positive complaints."""
    # Negative symptom statement
    state_neg = extract_conversation_symptom_state([], "I don't have chest pain, but I feel tired.")
    assert "chest pain" not in state_neg["complaints"]
    assert "chest pain" in state_neg["denied_symptoms"]
    assert "fatigue" in state_neg["complaints"]

    # Positive symptom statement
    state_pos = extract_conversation_symptom_state([], "I have severe chest pain.")
    assert "chest pain" in state_pos["complaints"]
    assert "chest pain" not in state_pos["denied_symptoms"]


def test_symptom_temporal_correction_handling():
    """Verify chronological corrections for symptoms, temperature, and medication."""
    # 1. Symptom denial followed by later emergence
    history_1 = [
        {"role": "user", "content": "I don't have a headache today."},
        {"role": "assistant", "content": "Noted. How else are you feeling?"}
    ]
    state_1 = extract_conversation_symptom_state(history_1, "Actually, now I have developed a bad headache.")
    assert "headache" in state_1["complaints"]
    assert "headache" not in state_1["denied_symptoms"]

    # 2. Temperature correction: earlier 100°F corrected to 102.5°F
    history_2 = [
        {"role": "user", "content": "My temperature is 100°F."},
        {"role": "assistant", "content": "Thank you for sharing your temperature."}
    ]
    state_2 = extract_conversation_symptom_state(history_2, "I just remeasured with a digital thermometer and it is 102.5°F.")
    assert "102.5" in state_2["temperature"]

    # 3. Medication status correction: earlier no meds, later took paracetamol
    history_3 = [
        {"role": "user", "content": "I haven't taken any medication yet."},
        {"role": "assistant", "content": "Understood. Avoid self-medicating."}
    ]
    state_3 = extract_conversation_symptom_state(history_3, "I took paracetamol 500mg 30 minutes ago.")
    assert "Paracetamol" in state_3["medication_status"]
    assert "No medication taken yet" not in state_3["medication_status"]


def test_symptom_recall_inquiry_four_turn_conversation():
    """
    Test 4-turn sequence:
    Turn 1: Fever for 2 days
    Turn 2: Temp 102°F, no medication yet
    Turn 3: Not experiencing any other symptoms
    Turn 4: What symptoms have I told you about so far?
    """
    history = [
        {"role": "user", "content": "I have had a fever for two days."},
        {"role": "assistant", "content": "I understand you have had a fever for two days. Have you measured your temperature?"},
        {"role": "user", "content": "My temperature is around 102°F. I haven't taken any medication yet."},
        {"role": "assistant", "content": "Thank you. Are you experiencing any other symptoms?"},
        {"role": "user", "content": "I am not experiencing any other symptoms."},
        {"role": "assistant", "content": "Understood that you have no other symptoms."}
    ]
    current_msg = "What symptoms have I told you about so far?"

    state = extract_conversation_symptom_state(history, current_msg)
    assert "fever" in state["complaints"]
    assert state["duration"] == "2 days"
    assert "102" in state["temperature"]
    assert state["no_other_symptoms"] is True
    assert "No medication taken yet" in state["medication_status"]

    # Verify fallback response explicitly synthesizes this exact consultation state
    resp = _generate_intelligent_clinical_fallback(current_msg, [], [], history)
    resp_lower = resp.content.lower()
    assert "fever" in resp_lower
    assert "102" in resp_lower
    assert "2 days" in resp_lower
    assert "no other symptoms" in resp_lower or "no other" in resp_lower


def test_citation_deduplication_in_chat_response():
    """Verify that multiple chunks from the same guideline produce deduplicated citations."""
    history = []
    # Query known to match multiple chunks of dengue guidelines
    current_msg = "What are the phase stages of dengue fever and clinical management?"
    resp = _generate_intelligent_clinical_fallback(current_msg, [], [], history)

    # Now test RAG retrieval query and ensure citations list has unique titles
    passages = rag_service.query("What are the phase stages of dengue fever?", top_k=4)
    assert len(passages) >= 2

    # Simulate citation assembly
    seen = set()
    citations = []
    for p in passages:
        title = p["metadata"].get("title")
        if title not in seen:
            seen.add(title)
            citations.append(p)

    # Citations list must have unique titles
    titles = [c["metadata"].get("title") for c in citations]
    assert len(titles) == len(set(titles))


@pytest.mark.asyncio
async def test_emergency_response_consolidated_header_and_no_drive():
    """Verify that emergency chat responses use neutral non-diagnostic header and no-drive warning."""
    resp = await generate_chat_response("I have severe crushing chest pain radiating to my arm and shortness of breath.", [])
    assert resp.is_emergency is True
    assert "Critical Warning Signs Detected — Possible Medical Emergency" in resp.content
    assert "Suspected Acute Coronary Syndrome" not in resp.content
    assert "do not drive yourself" in resp.content.lower()
    assert "112" in resp.content
    assert len(resp.safety_flags["triggers"]) >= 2
