"""
Independent Emergency Detection Safety Engine
Medically reviewed heuristic and deterministic rules for identifying critical emergency symptoms.
Runs independently of and prioritizes over LLM output.
"""
import re
from typing import Dict, Any, List, Optional
from backend.config import settings


class EmergencyDetectionResult:
    def __init__(
        self,
        is_emergency: bool,
        category: Optional[str] = None,
        triggers: Optional[List[str]] = None,
        urgency_code: str = "NON_EMERGENCY",
        guidance: Optional[str] = None,
        emergency_contacts: Optional[Dict[str, str]] = None
    ):
        self.is_emergency = is_emergency
        self.category = category or "None"
        self.triggers = triggers or []
        self.urgency_code = urgency_code
        self.guidance = guidance or ""
        self.emergency_contacts = emergency_contacts or {
            "National Emergency Helpline": settings.EMERGENCY_HELPLINE_INDIA,
            "Ambulance Services": settings.AMBULANCE_INDIA
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_emergency": self.is_emergency,
            "category": self.category,
            "triggers": self.triggers,
            "urgency_code": self.urgency_code,
            "guidance": self.guidance,
            "emergency_contacts": self.emergency_contacts
        }


# Negation pattern to prevent false triggers (e.g. "no chest pain", "chest pain has stopped")
NEGATION_PATTERNS = [
    r"\b(no|not|never|without|denies|ruled out|free of|resolved|stopped)\s+([a-z\s]{0,20})",
    r"\bnegative\s+for\b"
]


def _is_negated(text: str, match_start: int) -> bool:
    """Check if the matched trigger is preceded by negation in the same sentence or clause."""
    window = text[max(0, match_start - 35):match_start].lower()
    for pattern in NEGATION_PATTERNS:
        if re.search(pattern, window):
            return True
    return False


# Medically categorized emergency rule sets
EMERGENCY_RULESETS = [
    {
        "category": "Suspected Acute Coronary Syndrome / Cardiac Event",
        "primary_triggers": [
            r"\bcrushing\s+(chest\s+pain|chest\s+pressure|retrosternal\s+pain)\b",
            r"\bsevere\s+chest\s+pain\b",
            r"\bchest\s+tightness\s+(with|radiating)\b",
            r"\bpain\s+radiating\s+to\s+(left\s+arm|jaw|neck|back)\b",
            r"\bheart\s+attack\b"
        ],
        "associated_factors": [
            r"\bshortness\s+of\s+breath\b",
            r"\bdyspnea\b",
            r"\bcold\s+sweat\b",
            r"\bdiaphoresis\b",
            r"\bdizziness\b",
            r"\bnausea\b"
        ],
        "guidance": (
            "CRITICAL MEDICAL ALERT: Symptoms strongly suggest a possible acute cardiac event (such as a heart attack). "
            "DO NOT drive yourself to the hospital. Immediately dial 112 (National Emergency) or 102/108 for an ambulance. "
            "Sit in a comfortable, seated resting position while waiting for emergency responders."
        )
    },
    {
        "category": "Severe Acute Respiratory Distress",
        "primary_triggers": [
            r"\bcan('?t|not)\s+breathe\b",
            r"\bgasping\s+for\s+(air|breath)\b",
            r"\bsevere\s+(difficulty\s+breathing|breathlessness|shortness\s+of\s+breath)\b",
            r"\bblue\s+(lips|fingers|fingertips|skin|face)\b",
            r"\bcyanosis\b",
            r"\bchoking\b",
            r"\bstridor\b",
            r"\bunable\s+to\s+speak\s+in\s+sentences\b"
        ],
        "associated_factors": [],
        "guidance": (
            "CRITICAL MEDICAL ALERT: Severe breathing difficulty or oxygen depletion detected. "
            "This is a life-threatening emergency. Call 112 / 102 immediately. "
            "Sit upright to keep airways open and do not exert yourself."
        )
    },
    {
        "category": "Suspected Acute Stroke (FAST Protocol)",
        "primary_triggers": [
            r"\bfacial\s+droop(ing)?\b",
            r"\bface\s+(drooping|numb|sagging)\s+on\s+one\s+side\b",
            r"\barm\s+(weakness|numbness|drifting)\s+on\s+one\s+side\b",
            r"\bone\s+sided\s+(weakness|paralysis|numbness)\b",
            r"\bslurred\s+speech\b",
            r"\bunable\s+to\s+(speak|talk|form\s+words)\b",
            r"\bsudden\s+loss\s+of\s+speech\b",
            r"\bstroke\b",
            r"\bhemiparesis\b"
        ],
        "associated_factors": [],
        "guidance": (
            "CRITICAL MEDICAL ALERT: Potential stroke symptoms detected (FAST Protocol). "
            "Time lost is brain lost. Seek emergency hospital intervention IMMEDIATELY. "
            "Dial 112 / 102. Note the exact time when symptoms first started."
        )
    },
    {
        "category": "Severe Anaphylaxis / Acute Systemic Allergic Reaction",
        "primary_triggers": [
            r"\banaphylaxis\b",
            r"\bsevere\s+allergic\s+reaction\b",
            r"\bthroat\s+(closing|tightness|swelling)\b",
            r"\bswelling\s+of\s+(tongue|throat|lips)\s+(with|and)\s+(trouble|difficulty)\s+breathing\b"
        ],
        "associated_factors": [
            r"\bdizziness\b",
            r"\bfainting\b",
            r"\bhives\b",
            r"\bvomiting\b"
        ],
        "guidance": (
            "CRITICAL MEDICAL ALERT: Severe systemic allergic reaction / anaphylaxis suspected. "
            "If an epinephrine autoinjector (EpiPen) is prescribed and available, administer it immediately. "
            "Call 112 / 102 without delay."
        )
    },
    {
        "category": "Severe Uncontrolled Bleeding / Massive Trauma",
        "primary_triggers": [
            r"\bspurting\s+blood\b",
            r"\bsevere\s+uncontrolled\s+bleeding\b",
            r"\bgushing\s+blood\b",
            r"\bmassive\s+blood\s+loss\b",
            r"\bcoughing\s+up\s+large\s+amounts\s+of\s+blood\b",
            r"\bvomiting\s+(large\s+amounts\s+of\s+)?blood\b",
            r"\bhematemesis\b"
        ],
        "associated_factors": [],
        "guidance": (
            "CRITICAL MEDICAL ALERT: Acute massive hemorrhage detected. "
            "Apply continuous firm, direct pressure with a clean cloth. "
            "Call 112 / 102 immediately. Keep the patient warm and lying flat."
        )
    },
    {
        "category": "Neurological Crisis / Loss of Consciousness",
        "primary_triggers": [
            r"\bunconscious\b",
            r"\bunresponsive\b",
            r"\bpassed\s+out\s+and\s+(won'?t|cannot)\s+wake\s+up\b",
            r"\bactive\s+seizure\s+lasting\s+more\s+than\s+5\s+minutes\b",
            r"\bstatus\s+epilepticus\b",
            r"\bsudden\s+worst\s+headache\s+of\s+(my|their)\s+life\b",
            r"\bthunderclap\s+headache\b"
        ],
        "associated_factors": [],
        "guidance": (
            "CRITICAL MEDICAL ALERT: Altered consciousness or neurological emergency detected. "
            "Place patient in recovery position if breathing. Do not put anything in the mouth. "
            "Dial 112 / 102 for immediate emergency dispatch."
        )
    }
]


def detect_emergency(text: str, severity: Optional[int] = None) -> EmergencyDetectionResult:
    """
    Evaluates patient text and severity against clinical emergency criteria.
    Guarantees deterministic safety check unaffected by external LLM uptime or latency.
    """
    if not text:
        return EmergencyDetectionResult(is_emergency=False)

    text_lower = text.lower()
    matched_triggers = []
    triggered_category = None
    triggered_guidance = None

    # Check each emergency rule set
    for rule in EMERGENCY_RULESETS:
        category_matched = False
        cat_triggers = []

        for trig_pat in rule["primary_triggers"]:
            matches = list(re.finditer(trig_pat, text_lower))
            for m in matches:
                if not _is_negated(text_lower, m.start()):
                    category_matched = True
                    cat_triggers.append(m.group(0))

        if category_matched:
            # If primary triggers match, check if associated factors are required or present
            matched_triggers.extend(cat_triggers)
            triggered_category = rule["category"]
            triggered_guidance = rule["guidance"]
            break

    # Secondary check: High patient-reported severity (9 or 10) combined with acute high-risk keywords
    if not triggered_category and severity is not None and severity >= 9:
        high_risk_words = ["chest", "breathing", "heart", "head", "pain", "bleeding", "dizzy", "collapsed"]
        for hw in high_risk_words:
            if re.search(rf"\b{hw}\b", text_lower):
                matched_triggers.append(f"Severity rating {severity}/10 combined with acute symptom: {hw}")
                triggered_category = "Acute Severe Symptom Presentation (Score >= 9)"
                triggered_guidance = (
                    "URGENT ATTENTION: Patient-reported symptom severity is critically elevated (9-10/10). "
                    "Severe acute symptoms require immediate in-person emergency department evaluation. "
                    "Dial 112 or visit the nearest emergency room immediately."
                )
                break

    if triggered_category:
        return EmergencyDetectionResult(
            is_emergency=True,
            category=triggered_category,
            triggers=matched_triggers,
            urgency_code="EMERGENCY",
            guidance=triggered_guidance
        )

    return EmergencyDetectionResult(
        is_emergency=False,
        urgency_code="NON_EMERGENCY"
    )
