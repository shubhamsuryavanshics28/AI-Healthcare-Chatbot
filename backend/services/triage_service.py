"""
Structured Clinical Triage Service
Evaluates patient symptoms, duration, severity, and history into 4 preliminary urgency tiers:
1. EMERGENCY
2. URGENT
3. ROUTINE
4. SELF_CARE

SAFETY GUARANTEE: Uses independent deterministic rules to prevent LLM hallucination or downgrade.
"""
import re
from typing import Dict, Any, Optional
from backend.services.emergency_detector import detect_emergency


class TriageEvaluation:
    def __init__(
        self,
        urgency_level: str,
        guidance: str,
        rationale: str,
        recommended_timeframe: str,
        emergency_flag: bool = False,
        disclaimer: Optional[str] = None
    ):
        self.urgency_level = urgency_level
        self.guidance = guidance
        self.rationale = rationale
        self.recommended_timeframe = recommended_timeframe
        self.emergency_flag = emergency_flag
        self.disclaimer = disclaimer or (
            "Preliminary automated triage recommendation only. Not a medical diagnosis. "
            "If your condition worsens or you feel unwell, seek direct medical evaluation immediately."
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "urgency_level": self.urgency_level,
            "guidance": self.guidance,
            "rationale": self.rationale,
            "recommended_timeframe": self.recommended_timeframe,
            "emergency_flag": self.emergency_flag,
            "disclaimer": self.disclaimer
        }


def evaluate_triage(
    primary_symptom: str,
    duration: str,
    severity: int,
    frequency: Optional[str] = None,
    body_location: Optional[str] = None,
    associated_symptoms: Optional[str] = None,
    relevant_history: Optional[str] = None
) -> TriageEvaluation:
    """
    Evaluates patient information into a structured triage category.
    Runs independent emergency rules first; emergency results can never be downgraded.
    """
    combined_text = f"{primary_symptom}. {body_location or ''}. {associated_symptoms or ''}. {relevant_history or ''}"

    # Step 1: Check independent emergency detector
    emergency_res = detect_emergency(combined_text, severity=severity)
    if emergency_res.is_emergency:
        return TriageEvaluation(
            urgency_level="EMERGENCY",
            guidance=emergency_res.guidance,
            rationale=(
                f"Emergency red-flag symptom detected: '{emergency_res.category}' "
                f"(Triggers identified: {', '.join(emergency_res.triggers)}). "
                f"Reported severity: {severity}/10."
            ),
            recommended_timeframe="IMMEDIATE (Within minutes - Call Emergency Services 112 / 102)",
            emergency_flag=True
        )

    text_lower = combined_text.lower()
    duration_lower = (duration or "").lower()

    # Step 2: Check Urgent Medical Attention criteria (Within 4-12 hours / Same day clinic)
    is_urgent = False
    urgent_reasons = []

    if severity >= 7:
        is_urgent = True
        urgent_reasons.append(f"High symptom severity rating ({severity}/10)")

    # Urgent symptom markers
    urgent_keywords = [
        ("high fever", "Fever above 39°C / 102°F or accompanied by severe shivering"),
        ("vomiting blood", "Signs of gastrointestinal bleeding"),
        ("inability to keep liquids down", "Risk of severe dehydration"),
        ("severe abdominal pain", "Acute abdominal distress requiring surgical / medical clearance"),
        ("stiff neck with fever", "Potential meningeal irritation"),
        ("severe ear pain with discharge", "Acute middle ear infection risk"),
        ("asthma exacerbation", "Respiratory condition flare-up"),
        ("diabetic", "Underlying metabolic vulnerability during acute illness")
    ]

    for kw, reason in urgent_keywords:
        if kw in text_lower:
            is_urgent = True
            urgent_reasons.append(reason)

    if any(term in duration_lower for term in ["worsening rapidly", "sudden onset", "escalating"]):
        is_urgent = True
        urgent_reasons.append("Symptoms reported as rapidly deteriorating")

    if is_urgent:
        return TriageEvaluation(
            urgency_level="URGENT",
            guidance=(
                "You should seek in-person medical evaluation today (within 4 to 12 hours) "
                "at an urgent care clinic or outpatient hospital department. "
                "Do not wait several days for an appointment. "
                "If symptoms become more intense or any emergency warning signs develop, escalate to the emergency room immediately."
            ),
            rationale=f"Urgent evaluation indicated due to: {'; '.join(urgent_reasons)}.",
            recommended_timeframe="Within 4 to 12 hours (Same-day clinical visit)",
            emergency_flag=False
        )

    # Step 3: Check Routine Medical Consultation criteria (Within a few days)
    # Severity 4-6, or symptoms lasting longer than 5-7 days, or chronic recurring pattern
    is_routine = False
    routine_reasons = []

    if severity >= 4:
        is_routine = True
        routine_reasons.append(f"Moderate symptom severity ({severity}/10)")

    # Prolonged duration check: > 7 days, weeks, months, or persistent
    is_prolonged = False
    if any(ind in duration_lower for ind in ["week", "month", "lingering", "chronic", "persistent"]):
        is_prolonged = True
    else:
        # Check if duration specifies 7 or more days (e.g. "10 days", "14 days")
        days_match = re.search(r"\b(\d+)\s*day", duration_lower)
        if days_match and int(days_match.group(1)) >= 7:
            is_prolonged = True

    if is_prolonged:
        is_routine = True
        routine_reasons.append(f"Prolonged or ongoing symptom duration ({duration})")

    if any(term in text_lower for term in ["rash", "joint pain", "back pain", "fatigue", "indigestion", "cough", "allergy"]):
        is_routine = True
        routine_reasons.append("Symptom characteristics benefit from diagnostic evaluation")

    if is_routine:
        return TriageEvaluation(
            urgency_level="ROUTINE",
            guidance=(
                "Schedule a routine consultation with your primary healthcare physician within the next 2 to 3 days. "
                "Keep a written log of your symptoms, what triggers them, and any medications taken to share with your doctor. "
                "If your symptoms suddenly worsen or severe pain emerges, seek urgent care."
            ),
            rationale=f"Routine medical evaluation recommended due to: {'; '.join(routine_reasons)}.",
            recommended_timeframe="Within 2 to 3 days (Scheduled clinic appointment)",
            emergency_flag=False
        )

    # Step 4: Self-Care & Supportive Monitoring (Severity 1-3, short duration, mild common illness)
    return TriageEvaluation(
        urgency_level="SELF_CARE",
        guidance=(
            "Your symptoms appear mild and consistent with self-limiting conditions that may be managed with home supportive care. "
            "Ensure plenty of rest, maintain adequate oral hydration, and avoid strenuous physical exertion. "
            "Monitor your symptoms closely. If symptoms persist beyond 5-7 days or worsen in intensity, consult a healthcare professional."
        ),
        rationale=(
            f"Low severity rating ({severity}/10), mild symptom profile, and absence of red-flag warning signs."
        ),
        recommended_timeframe="Home supportive care; reassess in 48-72 hours",
        emergency_flag=False
    )
