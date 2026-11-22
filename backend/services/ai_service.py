"""
AI Healthcare Chatbot Service
Integrates AsyncOpenAI, prompt engineering, RAG grounding, emergency safety priority,
and graceful offline/error fallback mechanisms.
"""
import json
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
import openai

from backend.config import settings
from backend.services.emergency_detector import detect_emergency
from backend.services.rag_service import rag_service

# Asynchronous OpenAI client instance
_async_openai_client: Optional[AsyncOpenAI] = None


def get_async_openai() -> Optional[AsyncOpenAI]:
    global _async_openai_client
    if _async_openai_client is None and settings.OPENAI_API_KEY:
        _async_openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT_SECONDS
        )
    return _async_openai_client


SYSTEM_HEALTHCARE_PROMPT = """You are "ArogyaAI", a professional, compassionate, and trustworthy AI Healthcare Assistant designed for patient assistance and preliminary triage (Project ID: 26P_3CSE294).

CLINICAL & ETHICAL GUIDELINES:
1. NON-DIAGNOSTIC: You provide evidence-backed healthcare information, symptom explanations, and triage guidance. NEVER state a definitive medical diagnosis (e.g., avoid saying "You have pneumonia"; say "These symptoms may be associated with respiratory infections like bronchitis or pneumonia, which require a physician's evaluation").
2. NON-PRESCRIPTIVE: NEVER prescribe medications, specify personalized dosages, or recommend stopping prescribed medications. You may discuss general over-the-counter self-care principles if supported by clinical reference material.
3. RAG GROUNDING: When [MEDICAL REFERENCE PASSAGES] are provided in the prompt, strictly ground your factual statements on that evidence. Cite the source name and section. If the provided reference materials do not contain sufficient information, explicitly state: "The available medical reference guidelines do not contain specific information on this question; please consult a qualified healthcare provider."
4. STRUCTURED INQUIRY: If a patient describes a new symptom, ask up to 2-3 focused follow-up questions to understand:
   - Duration (how long has it lasted?)
   - Severity (on a scale of 1-10)
   - Associated symptoms (fever, rash, nausea, etc.)
5. EMERGENCY PRIORITY: If you detect any red-flag emergency symptoms (chest pain radiating to arm/jaw, acute shortness of breath, FAST stroke signs, severe hemorrhage, loss of consciousness), IMMEDIATELY advise the patient to dial 112 / 102 or go to the nearest emergency room.
6. EMPATHY & CLARITY: Use warm, clear, patient-friendly language. Avoid unnecessarily complex medical jargon without defining it.
"""


class AIChatResponse:
    def __init__(
        self,
        content: str,
        citations: List[Dict[str, Any]],
        safety_flags: Dict[str, Any],
        is_emergency: bool = False,
        tokens_used: int = 0
    ):
        self.content = content
        self.citations = citations
        self.safety_flags = safety_flags
        self.is_emergency = is_emergency
        self.tokens_used = tokens_used

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "citations": self.citations,
            "safety_flags": self.safety_flags,
            "is_emergency": self.is_emergency,
            "tokens_used": self.tokens_used
        }


async def generate_chat_response(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    patient_context: Optional[Dict[str, Any]] = None
) -> AIChatResponse:
    """
    Main chat generation pipeline:
    1. Independent Emergency Safety Check.
    2. RAG Medical Knowledge Retrieval.
    3. Patient Clinical Context Assembly.
    4. AsyncOpenAI Generation (or graceful fallback).
    """
    # Step 1: Independent Emergency Check
    emergency_eval = detect_emergency(user_message)
    if emergency_eval.is_emergency:
        emergency_content = (
            f"🚨 **IMMEDIATE EMERGENCY ALERT**\n\n"
            f"{emergency_eval.guidance}\n\n"
            f"**Detected Warning Signs:** {', '.join(emergency_eval.triggers)}\n\n"
            f"📞 **Emergency Contacts (India):**\n"
            f"- **National Emergency Helpline:** 112\n"
            f"- **Ambulance Services:** 102 / 108\n\n"
            f"*Please do not delay seeking professional emergency care.*"
        )
        return AIChatResponse(
            content=emergency_content,
            citations=[],
            safety_flags={
                "emergency_detected": True,
                "category": emergency_eval.category,
                "triggers": emergency_eval.triggers
            },
            is_emergency=True,
            tokens_used=0
        )

    # Step 2: RAG Medical Knowledge Retrieval
    rag_passages = rag_service.query(user_message, top_k=settings.RAG_TOP_K)
    citations = []
    rag_context_text = ""

    if rag_passages:
        context_parts = []
        for i, p in enumerate(rag_passages):
            meta = p["metadata"]
            citations.append({
                "title": meta.get("title", "Medical Reference"),
                "source": meta.get("source", "Official Medical Guideline"),
                "section": meta.get("section", ""),
                "url": meta.get("source_url", ""),
                "relevance_score": p.get("score", 0.0)
            })
            context_parts.append(
                f"[Source {i+1}: {meta.get('title', 'Unknown')} - {meta.get('section', '')}]\n{p['text']}"
            )
        rag_context_text = "\n\n".join(context_parts)

    # Step 3: Build Patient Context Summary
    patient_summary = ""
    if patient_context:
        conds = patient_context.get("conditions", [])
        allergies = patient_context.get("allergies", [])
        meds = patient_context.get("medications", [])
        parts = []
        if conds:
            parts.append(f"Known Conditions: {', '.join(conds)}")
        if allergies:
            parts.append(f"Allergies: {', '.join(allergies)}")
        if meds:
            parts.append(f"Current Medications: {', '.join(meds)}")
        if parts:
            patient_summary = f"[PATIENT MEDICAL BACKGROUND]: {'; '.join(parts)}"

    # Step 4: Call OpenAI or use Grounded Knowledge Fallback
    client = get_async_openai()

    if client and settings.OPENAI_API_KEY:
        messages = [{"role": "system", "content": SYSTEM_HEALTHCARE_PROMPT}]

        if patient_summary:
            messages.append({"role": "system", "content": patient_summary})

        if rag_context_text:
            messages.append({
                "role": "system",
                "content": f"[VERIFIED MEDICAL REFERENCE PASSAGES]:\n{rag_context_text}\n\nGround your clinical explanation on the above evidence where applicable."
            })

        # Add recent conversation turns (last 6 messages)
        recent_history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
        for turn in recent_history:
            messages.append({"role": turn["role"], "content": turn["content"]})

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        try:
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=0.3,  # Low temperature for factual precision
                max_tokens=650
            )
            ai_text = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0

            return AIChatResponse(
                content=ai_text,
                citations=citations,
                safety_flags={"emergency_detected": False, "grounded_rag": len(citations) > 0},
                is_emergency=False,
                tokens_used=tokens
            )
        except (openai.RateLimitError, openai.APITimeoutError, openai.AuthenticationError, openai.APIConnectionError, Exception) as e:
            print(f"[OpenAI Error] Chat completion error: {e}. Falling back to grounded knowledge engine.")
            return _generate_grounded_fallback(user_message, citations, rag_passages, error_msg=str(e))
    else:
        # No OpenAI API Key configured: Generate dynamic grounded response using retrieved RAG passages
        return _generate_grounded_fallback(user_message, citations, rag_passages)


def _generate_grounded_fallback(
    user_message: str,
    citations: List[Dict[str, Any]],
    rag_passages: List[Dict[str, Any]],
    error_msg: Optional[str] = None
) -> AIChatResponse:
    """
    Synthesizes a medically grounded response from retrieved RAG passages when OpenAI API is offline.
    Guarantees no crashes, accurate citations, and transparent communication.
    """
    if rag_passages:
        best_passage = rag_passages[0]
        meta = best_passage["metadata"]
        response_text = (
            f"Based on **{meta.get('title', 'Official Clinical Guidelines')}** "
            f"({meta.get('source', 'Health Authority')}):\n\n"
            f"{best_passage['text']}\n\n"
            f"**Key Clinical Takeaways:**\n"
            f"- **Section:** {meta.get('section', 'Clinical Guidelines')}\n"
            f"- **Review Date:** {meta.get('last_reviewed_date', 'Recent')}\n\n"
            f"💬 *To help assess your situation better: Could you tell me how long you have experienced this, and how severe it feels on a scale of 1 to 10?*\n\n"
            f"⚠️ *Medical Disclaimer: This information is for patient guidance only and does not replace a clinical examination.*"
        )
    else:
        response_text = (
            f"Thank you for reaching out. Based on your inquiry regarding *\"{user_message}\"*, "
            f"our current verified medical knowledge base does not contain an exact protocol match for this specific topic.\n\n"
            f"**General Clinical Advice:**\n"
            f"- For any new or concerning symptoms, please schedule an in-person consultation with a licensed healthcare practitioner.\n"
            f"- If you are experiencing sudden severe pain, high fever, or breathing difficulty, seek emergency medical care immediately.\n\n"
            f"💬 *If you have specific symptoms to assess, feel free to use the **Symptom Triage Assessment** tool from the menu above.*"
        )

    notice = " (Offline/Local Knowledge Mode)" if not error_msg else " (Local Grounded Fallback Mode)"

    return AIChatResponse(
        content=response_text,
        citations=citations,
        safety_flags={
            "emergency_detected": False,
            "fallback_mode": True,
            "mode_notice": notice,
            "error_detail": error_msg
        },
        is_emergency=False,
        tokens_used=0
    )
