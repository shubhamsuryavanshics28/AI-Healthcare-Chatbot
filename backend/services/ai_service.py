"""
AI Healthcare Chatbot Service (ArogyaAI - Project ID: 26P_3CSE294)
Implements an intelligent, evidence-grounded, empathetic conversational healthcare assistant.
Follows the clinical paradigm: Assist First -> Ask Next -> Personalize Continuously.
Incorporates independent emergency detection, RAG grounding, patient history awareness,
and robust offline clinical knowledge generation.
"""
import json
import re
from typing import List, Dict, Any, Optional, Tuple
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


SYSTEM_HEALTHCARE_PROMPT = """You are "ArogyaAI", a dedicated, compassionate, and intelligent AI Healthcare Assistant designed for patient assistance and preliminary triage (Project ID: 26P_3CSE294).

CORE CLINICAL METHODOLOGY:
Follow the "Assist First -> Ask Next -> Personalize Continuously" principle in all interactions:
1. ASSIST FIRST (Immediate Practical Self-Care):
   Whenever a patient mentions any symptom or health complaint, ALWAYS provide safe, practical, actionable relief measures in your very first response. Do not simply express sympathy or immediately bombard them with questions.
   Examples of practical assistance:
   - Hydration (water, electrolytes, warm fluids).
   - Resting in a calm, quiet, or darkened room.
   - Thermal comfort (cool or warm compresses, steam inhalation).
   - Postural comfort (elevating head, gentle stretching, lying on the side).
   - Light nourishment (if meals were skipped or stomach is upset).
   - Reducing screen exposure and bright lights for headaches/fatigue.
   - Trigger avoidance (spicy foods, allergens, heavy exertion).

2. POSSIBLE EXPLANATIONS (Non-Diagnostic):
   Provide brief, clear, reassuring explanations of common, benign possibilities (e.g., tension, eye strain, dehydration, mild viral infection, lack of sleep, dietary acidity).
   STRICT RULE: NEVER state a definitive diagnosis (avoid saying "You have X"; say "These symptoms are often seen in... or could be related to...").

3. ASK RELEVANT FOLLOW-UP QUESTIONS (1 to 3 max):
   Progressively ask 1 to 3 targeted, logical questions to better understand the situation:
   - Duration (when did it begin?)
   - Quality / Location (where is the pain, is it sharp/dull/throbbing?)
   - Severity (on a scale of 1 to 10)
   - Accompanying symptoms (fever, rash, nausea, etc.)
   CRITICAL CONVERSATION RULES:
   - NEVER ask 8 to 10 questions at once.
   - NEVER repeat questions that the patient has already answered earlier in the conversation history!
   - If the patient already told you the duration or severity in a previous message, acknowledge it and move forward.

4. WHEN TO SEEK MEDICAL CARE (Red Flags):
   Always explain clear warning signs and red flags that warrant visiting a clinic, consulting a doctor, or seeking immediate emergency care.

CONVERSATIONAL BEHAVIOR & TONE:
- Be warm, helpful, natural, and conversational, similar to a knowledgeable medical counselor.
- Handle greetings ("hello", "good morning", "how are you") warmly and briefly introduce how you can help.
- Understand spelling mistakes, informal phrasing, and incomplete sentences smoothly.
- Adapt subsequent responses based on prior answers:
  - If a patient says "since yesterday" -> acknowledge: "Since this has been present since yesterday..."
  - If a patient says "it is getting worse" -> recognize the escalation and appropriately prioritize medical evaluation.
  - If a patient reports duration >7-10 days -> recommend in-person medical evaluation.
- If a patient switches topics or mentions a new symptom, pivot seamlessly while noting relevant history.

MEDICATION SAFETY & PATIENT BACKGROUND:
- If [PATIENT MEDICAL BACKGROUND] is provided (Known Conditions, Allergies, Current Medications):
  - Actively cross-reference these when offering advice!
  - For example, if the patient has a known allergy or asthma or hypertension, ensure no suggested self-care conflicts with it.
- STRICT RULE: NEVER prescribe medications, specify custom prescription dosages, or tell a patient to discontinue prescribed treatments. General OTC information (e.g. oral rehydration salts, saline nasal drops) may be discussed with advice to consult a pharmacist or doctor.

EVIDENCE-BASED RAG GROUNDING:
- When [VERIFIED MEDICAL REFERENCE PASSAGES] are provided, ground your clinical points in that evidence and cite the source/section.
- If medical reference passages are NOT provided or do not match: draw upon your broad, safe, verified medical knowledge. NEVER say "our knowledge base does not contain an exact protocol match" or refuse to assist.
- NEVER invent fictitious medical sources, citations, or URLs.

EMERGENCY SUPREMACY:
- If acute red flags appear (crushing chest pain radiating to arm/jaw, acute shortness of breath, sudden facial drooping/speech loss, uncontrolled bleeding, severe trauma, anaphylaxis), IMMEDIATELY advise dialing 112 / 102 or reaching the nearest hospital.
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


def _classify_intent(user_message: str, history: List[Dict[str, str]]) -> str:
    """
    Classifies the user message intent to optimize RAG retrieval and response generation.
    Returns: 'GREETING', 'OUT_OF_SCOPE', 'FOLLOW_UP', 'SYMPTOM_OR_QUERY'
    """
    msg_clean = user_message.strip().lower()
    msg_words = re.findall(r"\b[a-z]+\b", msg_clean)

    # 1. Greetings
    greeting_patterns = [
        r"^(hi|hello|hey|hola|namaste|greetings)\b",
        r"^good\s+(morning|afternoon|evening|day)\b",
        r"^how\s+are\s+you\b",
        r"^who\s+are\s+you\b",
        r"^what\s+can\s+you\s+(do|help\s+with)\b",
        r"^help(\s+me)?$"
    ]
    for pat in greeting_patterns:
        if re.search(pat, msg_clean):
            # If message is just a greeting without symptoms, classify as GREETING
            if len(msg_words) <= 7 and not any(w in msg_clean for w in ["pain", "hurt", "fever", "cough", "sick", "ache", "doctor", "medicine"]):
                return "GREETING"

    # 2. Out of scope (non-medical inquiries)
    out_of_scope_patterns = [
        r"\b(stock|stocks|share\s+price|bitcoin|crypto|forex|trading)\b",
        r"\b(write\s+(a\s+)?(python|code|script|java|c\+\+|program))\b",
        r"\b(weather\s+in|recipe\s+for|movie\s+recommendation)\b"
    ]
    for pat in out_of_scope_patterns:
        if re.search(pat, msg_clean):
            return "OUT_OF_SCOPE"

    # 3. Short follow-up answer to a previous question
    follow_up_patterns = [
        r"^(since|for)\s+\d+\s+(day|days|hour|hours|week|weeks|month|months)",
        r"^(yesterday|today|last\s+night|this\s+morning)",
        r"^(it\s+is\s+)?(continuous|intermittent|constant|throbbing|sharp|dull|aching)",
        r"^(it\s+is\s+)?(getting\s+worse|worsening|better|improving|same|no\s+change)",
        r"^(getting\s+worse|worsening|better|improving|same|no\s+change)",
        r"^(\d{1,2}|about\s+\d{1,2}|scale\s+of\s+\d{1,2})(\s*\/\s*10)?$",
        r"^(yes|no|none|nothing|maybe|not\s+sure)\b",
        r"^(around|on)\s+(the\s+)?(forehead|back|temple|stomach|chest|neck|left|right)"
    ]
    if len(msg_words) <= 6 and history:
        for pat in follow_up_patterns:
            if re.search(pat, msg_clean):
                return "FOLLOW_UP"

    return "SYMPTOM_OR_QUERY"


def _extract_primary_complaint_from_history(history: List[Dict[str, str]]) -> str:
    """Finds the patient's primary complaint from prior turns in the conversation."""
    for turn in reversed(history):
        if turn.get("role") == "user":
            content = turn.get("content", "").lower()
            if any(term in content for term in ["headache", "fever", "cough", "throat", "pain", "stomach", "dizzy", "rash", "nausea", "tired", "back", "breath"]):
                return content
    return ""


async def generate_chat_response(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    patient_context: Optional[Dict[str, Any]] = None
) -> AIChatResponse:
    """
    Main chat generation pipeline:
    1. Independent Emergency Safety Check.
    2. Intent Classification (Greeting vs Follow-Up vs Clinical Query).
    3. RAG Medical Knowledge Retrieval (Targeted & Supportive).
    4. Patient Clinical Context Assembly.
    5. AsyncOpenAI Generation or Comprehensive Clinical Fallback Engine.
    """
    msg_stripped = user_message.strip()

    # Step 1: Independent Deterministic Emergency Check
    emergency_eval = detect_emergency(msg_stripped)
    if emergency_eval.is_emergency:
        emergency_content = (
            f"🚨 **IMMEDIATE EMERGENCY MEDICAL ALERT**\n\n"
            f"{emergency_eval.guidance}\n\n"
            f"**Detected Red Flags:** {', '.join(emergency_eval.triggers)}\n\n"
            f"📞 **Emergency Contacts (India):**\n"
            f"- **National Emergency Helpline:** 112\n"
            f"- **Ambulance Services:** 102 / 108\n\n"
            f"⚠️ *Please do not delay seeking professional emergency care. Sit in a comfortable resting position while help arrives.*"
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

    # Step 2: Intent Classification
    intent = _classify_intent(msg_stripped, conversation_history)

    # Step 3: Targeted RAG Retrieval (Avoid querying for simple greetings)
    citations = []
    rag_context_text = ""
    rag_passages = []

    if intent in ["SYMPTOM_OR_QUERY", "FOLLOW_UP"]:
        # For follow-ups, combine with past primary complaint if available for better retrieval
        search_query = msg_stripped
        if intent == "FOLLOW_UP":
            prior_complaint = _extract_primary_complaint_from_history(conversation_history)
            if prior_complaint:
                search_query = f"{prior_complaint} {msg_stripped}"

        rag_passages = rag_service.query(search_query, top_k=settings.RAG_TOP_K)

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

    # Step 4: Build Patient Context Summary
    patient_summary = ""
    if patient_context:
        demos = patient_context.get("demographics", [])
        conds = patient_context.get("conditions", [])
        allergies = patient_context.get("allergies", [])
        meds = patient_context.get("medications", [])
        parts = []
        if demos:
            parts.append(f"Demographics: {', '.join(demos)}")
        if conds:
            parts.append(f"Active Medical Conditions: {', '.join(conds)}")
        if allergies:
            parts.append(f"Known Drug/Food Allergies: {', '.join(allergies)}")
        if meds:
            parts.append(f"Current Prescribed Medications: {', '.join(meds)}")
        if parts:
            patient_summary = (
                f"[PATIENT MEDICAL BACKGROUND - Cross-reference for safety and contraindications]:\n"
                f"{'; '.join(parts)}"
            )

    # Step 5: Call OpenAI or use Intelligent Clinical Fallback
    client = get_async_openai()

    if client and settings.OPENAI_API_KEY:
        messages = [{"role": "system", "content": SYSTEM_HEALTHCARE_PROMPT}]

        if patient_summary:
            messages.append({"role": "system", "content": patient_summary})

        if rag_context_text:
            messages.append({
                "role": "system",
                "content": (
                    f"[VERIFIED MEDICAL REFERENCE PASSAGES]:\n{rag_context_text}\n\n"
                    f"Use the above reference passages to ground your factual explanations and cite the source name. "
                    f"If the passages do not fully cover the user's specific symptom, supplement with safe general clinical guidance "
                    f"following the 'Assist First -> Ask Next' principle."
                )
            })

        # Add recent conversation turns (up to 8 messages to maintain strong memory)
        recent_history = conversation_history[-8:] if len(conversation_history) > 8 else conversation_history
        for turn in recent_history:
            messages.append({"role": turn["role"], "content": turn["content"]})

        # Add current user message
        messages.append({"role": "user", "content": msg_stripped})

        try:
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=0.4,
                max_tokens=750
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
            print(f"[OpenAI Error] Chat completion error: {e}. Executing intelligent clinical fallback engine.")
            return _generate_intelligent_clinical_fallback(
                msg_stripped,
                citations,
                rag_passages,
                conversation_history,
                patient_context,
                error_msg=str(e)
            )
    else:
        # No OpenAI API Key configured: Execute intelligent clinical fallback engine
        return _generate_intelligent_clinical_fallback(
            msg_stripped,
            citations,
            rag_passages,
            conversation_history,
            patient_context
        )


def _generate_intelligent_clinical_fallback(
    user_message: str,
    citations: List[Dict[str, Any]],
    rag_passages: List[Dict[str, Any]],
    conversation_history: List[Dict[str, str]],
    patient_context: Optional[Dict[str, Any]] = None,
    error_msg: Optional[str] = None
) -> AIChatResponse:
    """
    Intelligent, safe clinical knowledge engine.
    Ensures that ArogyaAI NEVER outputs robotic 'no exact protocol match' messages.
    Always follows: Assist First -> Possible Explanations -> Ask Next -> Red Flags.
    """
    msg_lower = user_message.lower().strip()
    intent = _classify_intent(user_message, conversation_history)

    # 1. Greeting Handling
    if intent == "GREETING":
        response_text = (
            "Hello! I am **ArogyaAI**, your healthcare assistant and preliminary triage guide.\n\n"
            "I can help you by:\n"
            "- Providing safe, immediate practical guidance for common symptoms.\n"
            "- Explaining possible health factors and self-care steps.\n"
            "- Helping you evaluate the urgency of your symptoms and identifying red flags.\n"
            "- Checking verified medical references (WHO, CDC, FDA, MoHFW India).\n\n"
            "💬 *How can I assist you with your health today? Please feel free to describe what you are experiencing.*"
        )
        return AIChatResponse(
            content=response_text,
            citations=[],
            safety_flags={"emergency_detected": False, "intent": "greeting"},
            is_emergency=False,
            tokens_used=0
        )

    # 2. Out of Scope Handling
    if intent == "OUT_OF_SCOPE":
        response_text = (
            "I am designed specifically as a **clinical healthcare and triage assistant**. "
            "I cannot assist with financial, programming, or non-medical topics.\n\n"
            "If you or someone in your family has a question about health, medications, symptoms, "
            "or wellness guidelines, please let me know and I will be happy to provide practical guidance!"
        )
        return AIChatResponse(
            content=response_text,
            citations=[],
            safety_flags={"emergency_detected": False, "intent": "out_of_scope"},
            is_emergency=False,
            tokens_used=0
        )

    # 3. Follow-up handling (User answering previous questions)
    if intent == "FOLLOW_UP":
        prior_complaint = _extract_primary_complaint_from_history(conversation_history)
        symptom_name = "symptom"
        if "headache" in prior_complaint:
            symptom_name = "headache"
        elif "fever" in prior_complaint:
            symptom_name = "fever"
        elif "cough" in prior_complaint or "cold" in prior_complaint:
            symptom_name = "cough"
        elif "stomach" in prior_complaint:
            symptom_name = "stomach pain"

        # Check if worsening
        if any(w in msg_lower for w in ["getting worse", "worse", "worsening", "severe", "more painful"]):
            response_text = (
                f"Thank you for sharing that update. Because your **{symptom_name} is getting worse**, "
                f"it is important to exercise extra caution.\n\n"
                f"### 📋 Recommended Next Steps\n"
                f"- **Medical Evaluation Recommended:** Since symptoms are intensifying rather than improving, an in-person assessment by a physician or urgent care clinic is strongly advised.\n"
                f"- **Continue Baseline Rest:** Keep resting, avoid strenuous physical or mental activity, and maintain gentle hydration.\n"
                f"- **Track Severity:** If you feel the pain reaches an unbearable level (8-10/10) or begins interfering with your daily functioning, do not wait.\n\n"
                f"### 🚨 Warning Signs Requiring Immediate Emergency Care\n"
                f"- Sudden explosive onset or worst pain of your life.\n"
                f"- Accompanying high fever, stiff neck, vomiting, or confusion.\n"
                f"- Difficulty speaking, facial drooping, or limb weakness.\n"
                f"- Shortness of breath or chest discomfort.\n\n"
                f"💬 *Are you experiencing any of these warning signs, or any nausea or vision changes?*"
            )
            return AIChatResponse(
                content=response_text,
                citations=citations,
                safety_flags={"emergency_detected": False, "followup_progression": "worsening"},
                is_emergency=False,
                tokens_used=0
            )

        # General follow-up acknowledgement
        response_text = (
            f"Understood. Thank you for clarifying that detail regarding your {symptom_name}.\n\n"
            f"### 🌿 What You Can Do Right Now\n"
            f"- **Supportive Care:** Maintain adequate hydration with room-temperature water or electrolytes.\n"
            f"- **Rest:** Give your body time to recuperate in a comfortable, quiet setting.\n"
            f"- **Monitor Progression:** Keep track of whether the sensation remains steady, subsides with rest, or shifts in location.\n\n"
            f"### 🔍 To Help Narrow Down the Picture\n"
            f"- On a scale of 1 to 10, how intense would you rate this right now?\n"
            f"- Have you noticed any other symptoms alongside it (such as mild fever, nausea, or dizziness)?\n\n"
            f"⚠️ *If you develop sudden sharp escalation, severe weakness, or breathing difficulties, please seek immediate medical evaluation.*"
        )
        return AIChatResponse(
            content=response_text,
            citations=citations,
            safety_flags={"emergency_detected": False, "followup_progression": "standard"},
            is_emergency=False,
            tokens_used=0
        )

    # 4. Check for Symptom-specific Clinical Responses (Assist First -> Ask Next -> Red Flags)
    # Case A: Headache
    if any(k in msg_lower for k in ["headache", "head ache", "head hurts", "pain in head", "migraine"]):
        response_text = (
            "I understand you are dealing with a headache. Let's look at some immediate steps you can take to find relief:\n\n"
            "### 🌿 What You Can Do Right Now\n"
            "- **Hydrate Immediately:** Drink a full glass of water. Mild dehydration is one of the most common headache triggers.\n"
            "- **Rest in a Quiet, Dim Room:** Turn down bright overhead lights and rest away from screens (phones, computers, TVs).\n"
            "- **Apply a Compress:** A cool, damp washcloth across the forehead can soothe tension, or a warm compress on the back of the neck can ease tight muscles.\n"
            "- **Check Meal Timing:** If you have gone several hours without eating, have a light, nutritious snack.\n"
            "- **Gentle Neck & Shoulder Release:** Slowly roll your shoulders and gently stretch neck muscles to relieve tension.\n\n"
            "### 🔍 What Might Be Causing It\n"
            "Headaches are very common and frequently related to:\n"
            "- Tension, stress, or posture strain from prolonged computer work.\n"
            "- Dehydration or skipping meals.\n"
            "- Insufficient or disrupted sleep.\n"
            "- Eye strain or sinus congestion.\n\n"
            "### ❓ A Few Questions to Understand Better\n"
            "1. When did this headache start, and is it constant or coming in waves?\n"
            "2. Where is the pain located (e.g. forehead, temples, back of head, or one side)?\n"
            "3. On a scale of 1 to 10, how severe is the pain?\n\n"
            "### 🚨 When to Seek Immediate Medical Attention\n"
            "Seek urgent medical care (or dial **112**) if you experience:\n"
            "- A sudden, explosive 'thunderclap' headache reaching maximum intensity in seconds.\n"
            "- Headache accompanied by a stiff neck, high fever, or vomiting.\n"
            "- Any facial drooping, arm weakness, slurred speech, or vision loss."
        )

    # Case B: Fever
    elif any(k in msg_lower for k in ["fever", "high temperature", "chills", "feeling hot and cold"]):
        response_text = (
            "Dealing with a fever can be draining. Here are practical steps to help your body manage it safely:\n\n"
            "### 🌿 What You Can Do Right Now\n"
            "- **Stay Thoroughly Hydrated:** Drink plenty of fluids (water, oral rehydration solutions, clear broths, or coconut water) to replenish fluids lost through sweating.\n"
            "- **Rest in a Cool Environment:** Wear light, breathable cotton clothing and keep room temperature comfortable. Avoid heavy blankets which trap heat.\n"
            "- **Tepid Sponge Baths:** If feeling uncomfortably hot, use a washcloth with lukewarm (not cold) water across forehead and neck.\n"
            "- **Monitor Temperature:** Check and record your temperature every 4–6 hours with a thermometer.\n\n"
            "### 🔍 What Might Be Causing It\n"
            "Fever is your body's natural defense mechanism, commonly triggered by viral infections (such as the common cold, flu, or seasonal viral fevers) or localized infections.\n\n"
            "### ❓ A Few Questions to Help Assess\n"
            "1. What is your current temperature reading, and how many days has the fever lasted?\n"
            "2. Are you experiencing other symptoms, such as severe body ache, cough, sore throat, or joint pain?\n"
            "3. Have you traveled recently or been in an area with dengue/malaria reports?\n\n"
            "### 🚨 Red Flags Requiring Immediate Medical Attention\n"
            "- Fever exceeding 103°F (39.4°C) or not responding to baseline care.\n"
            "- Difficulty breathing, persistent vomiting, or inability to keep fluids down.\n"
            "- Stiff neck, extreme lethargy, confusion, or a new unexplained skin rash.\n"
            "- Bleeding from gums/nose or tiny red spots on the skin (petechiae)."
        )

    # Case C: Cough / Cold / Sore Throat
    elif any(k in msg_lower for k in ["cough", "cold", "sore throat", "throat pain", "runny nose", "congestion", "scratchy"]):
        response_text = (
            "A sore throat and cold can be very uncomfortable. Here are safe, practical steps to soothe irritation right now:\n\n"
            "### 🌿 What You Can Do Right Now\n"
            "- **Warm Salt Water Gargle:** Dissolve 1/2 teaspoon of table salt in a glass of warm water. Gargle for 30 seconds 3–4 times daily to reduce throat swelling.\n"
            "- **Soothe with Warm Liquids:** Sip warm water with a teaspoon of honey (for adults and children over 1 year), herbal tea, or warm clear broth.\n"
            "- **Steam Inhalation:** Inhale steam from a bowl of hot water or take a warm shower to loosen chest and nasal congestion.\n"
            "- **Elevate Your Head at Night:** Use an extra pillow to prevent mucus from pooling in the back of your throat while sleeping.\n"
            "- **Rest Your Voice:** Avoid shouting or whispering strain if your voice feels hoarse.\n\n"
            "### 🔍 What Might Be Causing It\n"
            "Most acute sore throats and coughs are caused by common respiratory viruses. They typically run their course in 5 to 7 days with supportive self-care.\n\n"
            "### ❓ A Few Helpful Questions\n"
            "1. How long have you had this cough or throat irritation?\n"
            "2. Is the cough dry or productive (bringing up phlegm)? If productive, what color is the mucus?\n"
            "3. Do you have a fever, or difficulty swallowing liquids?\n\n"
            "### 🚨 Warning Signs to Watch For\n"
            "- Difficulty breathing, stridor (high-pitched breathing sound), or shortness of breath.\n"
            "- Inability to swallow your own saliva or fluids.\n"
            "- Coughing up visible blood or rust-colored phlegm.\n"
            "- Symptoms persisting beyond 10–14 days without improvement."
        )

    # Case D: Stomach Pain / Acidity / Indigestion / Nausea
    elif any(k in msg_lower for k in ["stomach", "belly", "abdomen", "acid", "acidity", "indigestion", "nausea", "vomit", "heartburn", "bloating"]):
        response_text = (
            "Stomach discomfort is unpleasant and can arise from many simple daily factors. Here are safe immediate measures:\n\n"
            "### 🌿 What You Can Do Right Now\n"
            "- **Stay Upright:** Avoid lying down flat immediately after meals. If resting, keep your upper body elevated at a 30–45 degree angle.\n"
            "- **Sip Fluids Slowly:** Sip room-temperature water or diluted oral rehydration salts (ORS) in small, frequent sips rather than gulping.\n"
            "- **Gentle Nutrition (BRAT principles):** If hungry, stick to bland, easily digestible foods like bananas, rice, toast, or clear soup. Avoid spicy, oily, or acidic foods.\n"
            "- **Apply Mild Warmth:** A warm hot-water bottle or heating pad placed on the abdomen can help ease muscle cramping.\n"
            "- **Avoid NSAIDs:** Do not take ibuprofen or aspirin for stomach pain, as they can further irritate the stomach lining.\n\n"
            "### 🔍 What Might Be Causing It\n"
            "Common causes include acid reflux, mild indigestion from heavy or spicy meals, viral gastroenteritis, or gas accumulation.\n\n"
            "### ❓ A Few Questions to Understand Better\n"
            "1. Where exactly is the pain located (e.g. upper stomach, around the navel, or lower right side)?\n"
            "2. Is the pain sharp, cramping, or a burning sensation?\n"
            "3. Have you experienced vomiting, diarrhea, or fever?\n\n"
            "### 🚨 Red Flags Requiring Immediate Medical Attention\n"
            "- Severe, unbearable abdominal pain that makes it painful to walk or touch the belly.\n"
            "- Vomiting blood or material that looks like dark coffee grounds.\n"
            "- Black, tarry bowel movements.\n"
            "- Pain starting around the belly button and migrating to the lower right abdomen with fever."
        )

    # Case E: Fatigue / Tiredness / Weakness
    elif any(k in msg_lower for k in ["tired", "fatigue", "exhausted", "weakness", "low energy", "sleepy"]):
        response_text = (
            "Experiencing persistent fatigue can significantly impact your day. Here are immediate supportive steps to consider:\n\n"
            "### 🌿 What You Can Do Right Now\n"
            "- **Hydrate & Replenish:** Drink a tall glass of water. Even slight cellular dehydration noticeably reduces energy and focus.\n"
            "- **Balanced Nourishment:** Have a wholesome snack containing complex carbohydrates and protein (e.g. fruit with nuts, or yogurt) to stabilize blood sugar.\n"
            "- **Step into Daylight:** Spend 10–15 minutes in natural sunlight to reset your circadian rhythm and alertness.\n"
            "- **Take a Brief Rest:** A short 20-minute power nap can restore alertness without causing sleep inertia.\n"
            "- **Review Sleep Hygiene:** Aim for 7–8 hours of uninterrupted sleep tonight in a cool, dark bedroom with screens turned off 45 minutes before bed.\n\n"
            "### 🔍 What Might Be Causing It\n"
            "Fatigue is most commonly linked to lifestyle factors such as sleep deficit, sustained mental stress, poor hydration, or recovery from a recent viral illness. In other cases, it may point towards mild anemia, vitamin D deficiency, or thyroid imbalances.\n\n"
            "### ❓ A Few Questions to Help Understand\n"
            "1. How long have you felt this level of fatigue (a few days, weeks, or months)?\n"
            "2. Are you getting 7–8 hours of restful sleep at night, or waking up frequently?\n"
            "3. Do you have other symptoms such as shortness of breath with mild activity, dizziness, or unintentional weight changes?\n\n"
            "### 🚨 When to See a Doctor\n"
            "- Unexplained, severe fatigue lasting longer than 2–3 weeks despite adequate rest.\n"
            "- Accompanied by chest pressure, shortness of breath, sudden muscle weakness, or fainting."
        )

    # Case F: Specific Medical Guidelines from RAG match (e.g. Dengue, Hypertension, Diabetes, Influenza, Paracetamol)
    elif rag_passages:
        best_passage = rag_passages[0]
        meta = best_passage["metadata"]
        title = meta.get("title", "Clinical Guidelines")
        source = meta.get("source", "Health Authority")
        section = meta.get("section", "Guidelines")

        response_text = (
            f"### 📚 Evidence-Based Clinical Guidance\n"
            f"Based on **{title}** ({source} • *{section}*):\n\n"
            f"{best_passage['text']}\n\n"
            f"### 🌿 What You Can Do Right Now\n"
            f"- Follow recommended rest and hydration protocols.\n"
            f"- Closely observe for any warning signs or changes in symptom intensity.\n"
            f"- Consult a healthcare professional before initiating or modifying any medication.\n\n"
            f"### 💬 Questions to Help Me Assist You Better\n"
            f"1. How long have you been experiencing these symptoms?\n"
            f"2. How severe is the discomfort on a scale of 1 to 10?\n"
            f"3. Do you have any known medical conditions or active medications?\n\n"
            f"⚠️ *Medical Disclaimer: This information is for patient educational guidance and preliminary triage only.*"
        )
        return AIChatResponse(
            content=response_text,
            citations=citations,
            safety_flags={"emergency_detected": False, "grounded_rag": True},
            is_emergency=False,
            tokens_used=0
        )

    # Case F: General / Other Health Complaints
    else:
        response_text = (
            f"Thank you for sharing your concern regarding *\"{user_message}\"*. "
            f"Let's look at safe, practical steps you can take while we assess this further:\n\n"
            f"### 🌿 What You Can Do Right Now\n"
            f"- **Rest in Comfort:** Take a break from strenuous physical exertion and rest in a comfortable, relaxed environment.\n"
            f"- **Stay Hydrated:** Sip adequate water or clear fluids throughout the day.\n"
            f"- **Avoid Self-Medicating:** Avoid taking unverified medications or changing your prescribed regimen before consulting a doctor.\n"
            f"- **Keep a Symptom Log:** Note down when the discomfort feels strongest, what relieves it, and what makes it worse.\n\n"
            f"### ❓ Questions to Understand Your Situation Better\n"
            f"1. When did this issue first begin, and how often does it occur?\n"
            f"2. On a scale of 1 to 10, how severe would you rate the discomfort?\n"
            f"3. Are there any other symptoms you are noticing along with it?\n\n"
            f"### 🚨 When to Seek In-Person Medical Attention\n"
            f"- If symptoms are rapidly worsening or interfering with your normal daily routine.\n"
            f"- If you experience severe pain, high fever, chest tightness, or breathing difficulties.\n\n"
            f"💬 *Please share a few more details so I can provide more personalized guidance for you.*"
        )

    return AIChatResponse(
        content=response_text,
        citations=citations,
        safety_flags={"emergency_detected": False, "clinical_guidance": True},
        is_emergency=False,
        tokens_used=0
    )
