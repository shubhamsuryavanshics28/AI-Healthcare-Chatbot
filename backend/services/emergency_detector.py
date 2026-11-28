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
        "category": "Potential Cardiac / Cardiovascular Warning Signs",
        "primary_triggers": [
            r"\bcrushing\s+(chest\s+pain|chest\s+pressure|retrosternal\s+pain)\b",
            r"\bsevere\s+chest\s+pain\b",
            r"\bchest\s+tightness\s+(with|radiating)\b",
            r"\bpain\s+radiating\s+to\s+(left\s+arm|jaw|neck|back)\b",
            r"\b(ripping|tearing)\s+(chest|back)\s+pain\b",
            r"\b(ripping|tearing)\s+pain\s+(in|between|across)\b",
            r"\baortic\s+dissection\b",
            r"\b(bp|blood\s+pressure).*?(1[89]\d|2\d\d)\/(1[1-9]\d|2\d\d)\b",
            r"\bhypertensive\s+crisis\b",
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
            "CRITICAL MEDICAL ALERT: These symptoms may indicate a serious medical emergency, including a possible heart or cardiovascular condition. "
            "DO NOT drive yourself to the hospital. Immediately dial 112 (National Emergency Helpline) or 102 / 108 for emergency ambulance services. "
            "Sit in a comfortable, seated resting position while waiting for emergency responders."
        )
    },
    {
        "category": "Potential Severe Respiratory Distress / Airway Warning Signs",
        "primary_triggers": [
            r"\bcan('?t|not)\s+breathe\b",
            r"\bgasping\s+for\s+(air|breath)\b",
            r"\bsevere\s+(difficulty\s+breathing|breathlessness|shortness\s+of\s+breath)\b",
            r"\bblue\s+(lips|fingers|fingertips|skin|face)\b",
            r"\b(lips|skin|face|fingers)\s+(turning|are)\s+blue\b",
            r"\bturning\s+(purple|blue)\b",
            r"\bcyanosis\b",
            r"\bchoking\b",
            r"\bclutching\s+(at\s+)?(throat|neck)\b",
            r"\bstridor\b",
            r"\bunable\s+to\s+speak\s+in\s+sentences\b",
            r"\bunable\s+to\s+(breathe|cough|speak|cry)\b",
            r"\bforeign\s+body\s+airway\b",
            r"\bpneumothorax\b"
        ],
        "associated_factors": [],
        "guidance": (
            "CRITICAL MEDICAL ALERT: Severe breathing difficulty or airway compromise detected. "
            "This is a serious medical emergency. DO NOT drive yourself. Immediately call 112 or 102 / 108 for emergency ambulance services. "
            "Sit upright to keep airways open while emergency responders are en route."
        )
    },
    {
        "category": "Potential Stroke Warning Signs (FAST Protocol)",
        "primary_triggers": [
            r"\bfacial\s+droop(ing)?\b",
            r"\bface\s+(is\s+)?(drooping|numb|sagging)\b",
            r"\bface\s+(drooping|numb|sagging)\s+on\s+one\s+side\b",
            r"\bside\s+of\s+(the\s+)?face\s+(is\s+)?(drooping|numb|sagging)\b",
            r"\barm\s+(weakness|numbness|drifting)\s+on\s+one\s+side\b",
            r"\barm\s+(is\s+)?weak\s+and\s+cannot\s+lift\b",
            r"\bone\s+sided\s+(weakness|paralysis|numbness)\b",
            r"\bslurred\s+speech\b",
            r"\bunable\s+to\s+(speak|talk|form\s+words)\b",
            r"\bsudden\s+loss\s+of\s+speech\b",
            r"\bstroke\b",
            r"\bhemiparesis\b"
        ],
        "associated_factors": [],
        "guidance": (
            "CRITICAL MEDICAL ALERT: Symptoms consistent with acute neurological warning signs (FAST: Face, Arms, Speech, Time) detected. "
            "Immediate hospital evaluation is essential. DO NOT drive yourself. "
            "Dial 112 or 102 / 108 immediately for an ambulance. Note the exact time when symptoms first began."
        )
    },
    {
        "category": "Potential Severe Allergic Reaction / Anaphylaxis Warning Signs",
        "primary_triggers": [
            r"\banaphylaxis\b",
            r"\bsevere\s+allergic\s+reaction\b",
            r"\bthroat\s+(is\s+)?(closing|closing\s+up|tightness|swelling)\b",
            r"\btongue\s+(is\s+)?swollen\b",
            r"\bswollen\s+(tongue|throat|lips)\b",
            r"\bswelling\s+of\s+(tongue|throat|lips)\b"
        ],
        "associated_factors": [
            r"\bdizziness\b",
            r"\bfainting\b",
            r"\bhives\b",
            r"\bvomiting\b"
        ],
        "guidance": (
            "CRITICAL MEDICAL ALERT: Possible severe systemic allergic reaction (anaphylaxis) detected. "
            "If an epinephrine autoinjector (EpiPen) has been prescribed and is available, administer it immediately as directed. "
            "Call 112 or 102 / 108 without delay. Do not drive yourself."
        )
    },
    {
        "category": "Potential Severe Bleeding / Trauma Warning Signs",
        "primary_triggers": [
            r"\bspurting\s+blood\b",
            r"\bsevere\s+uncontrolled\s+bleeding\b",
            r"\bgushing\s+blood\b",
            r"\bmassive\s+blood\s+loss\b",
            r"\bcoughing\s+up\s+(large\s+amounts\s+of\s+)?blood\b",
            r"\bhemoptysis\b",
            r"\bvomiting\s+(large\s+amounts\s+of\s+)?blood\b",
            r"\bcoffee\s+ground(s)?\b",
            r"\b(black|tarry)\s+(stool(s)?|bowel\s+movement(s)?)\b",
            r"\bhematemesis\b",
            r"\bmelena\b",
            r"\bbone\s+(sticking\s+through|protruding|poking\s+out)\b",
            r"\bcompound\s+fracture\b",
            r"\bopen\s+fracture\b"
        ],
        "associated_factors": [],
        "guidance": (
            "CRITICAL MEDICAL ALERT: Acute massive bleeding or serious physical trauma detected. "
            "Apply continuous firm, direct pressure with a clean cloth for external bleeding. Do not move broken bones. "
            "Call 112 or 102 / 108 immediately. Keep the person calm, warm, and lying flat while awaiting responders."
        )
    },
    {
        "category": "Potential Neurological Crisis Warning Signs",
        "primary_triggers": [
            r"\bunconscious\b",
            r"\bunresponsive\b",
            r"\bpassed\s+out\s+and\s+(won'?t|cannot)\s+wake\s+up\b",
            r"\bactive\s+seizure\b",
            r"\bconvulsing\b",
            r"\bfoaming\s+at\s+(the\s+)?mouth\b",
            r"\bstatus\s+epilepticus\b",
            r"\bsudden\s+worst\s+(headache|pain)\s+of\s+(my|their)\s+(entire\s+)?life\b",
            r"\bworst\s+pain\s+of\s+my\s+entire\s+life\b",
            r"\bthunderclap\s+headache\b",
            r"\bneck\s+stiffness\s+(with|and)\s+.*fever\b",
            r"\bunable\s+to\s+touch\s+chin\s+to\s+chest\b",
            r"\bmeningitis\b"
        ],
        "associated_factors": [],
        "guidance": (
            "CRITICAL MEDICAL ALERT: Acute neurological warning signs or altered responsiveness detected. "
            "Place the person in the recovery position if breathing. Do not put anything in the mouth. "
            "Dial 112 or 102 / 108 for immediate emergency medical dispatch."
        )
    },
    {
        "category": "Potential Acute Metabolic Crisis / Toxicity Warning Signs",
        "primary_triggers": [
            r"\b(fruity|acetone)\s+(breath|odor)\b",
            r"\bdiabetic\s+ketoacidosis\b",
            r"\bdka\b",
            r"\b(blood\s+sugar|glucose)\s+(is\s+|reading\s+is\s+)?(3[5-9]|[12]\d)\s*(mg\/dl)?\b",
            r"\bhow\s+many\s+.*pills\s+(cause\s+death|to\s+die|are\s+fatal|lethal)\b",
            r"\bdistended\s+hard\s+belly.*vomiting\s+green\s+bile\b",
            r"\bbowel\s+obstruction\b"
        ],
        "associated_factors": [],
        "guidance": (
            "CRITICAL MEDICAL ALERT: Severe metabolic or potential toxicity symptoms detected. "
            "Immediate emergency department evaluation is necessary. Dial 112 or 102 / 108 without delay. Do not attempt to drive yourself."
        )
    },
    {
        "category": "Crisis & Mental Health Support Alert",
        "primary_triggers": [
            r"\b(want\s+to\s+end\s+my\s+life|kill\s+myself|commit\s+suicide|self[\s-]harm)\b",
            r"\bfeel\s+hopeless\s+and\s+.*want\s+to\s+end\s+my\s+life\b"
        ],
        "associated_factors": [],
        "guidance": (
            "CRISIS ALERT: You are not alone, and help is available right now. "
            "If you are in distress, please reach out immediately: "
            "India Tele-MANAS Mental Health Helpline: 14416 or 1800-891-4416 (24x7 Free) | "
            "Kiran Mental Health Helpline: 1800-599-0019 | National Emergency: 112."
        )
    }
]


def detect_emergency(text: str, severity: Optional[int] = None) -> EmergencyDetectionResult:
    """
    Evaluates patient text and severity against clinical emergency criteria.
    Guarantees deterministic safety check unaffected by external LLM uptime or latency.
    Extracts ALL distinct red flags and associated factors present across all rule sets.
    """
    if not text:
        return EmergencyDetectionResult(is_emergency=False)

    text_lower = text.lower()
    matched_triggers = []
    matched_categories = []
    primary_guidance = None

    # Check each emergency rule set
    for rule in EMERGENCY_RULESETS:
        cat_triggers = []

        for trig_pat in rule["primary_triggers"]:
            matches = list(re.finditer(trig_pat, text_lower))
            for m in matches:
                if not _is_negated(text_lower, m.start()):
                    matched_str = m.group(0).strip()
                    if matched_str not in cat_triggers and matched_str not in matched_triggers:
                        cat_triggers.append(matched_str)

        if cat_triggers:
            matched_triggers.extend(cat_triggers)
            matched_categories.append(rule["category"])
            if not primary_guidance:
                primary_guidance = rule["guidance"]

            # Also extract any associated factors mentioned (e.g. shortness of breath, dizziness)
            for assoc_pat in rule.get("associated_factors", []):
                assoc_matches = list(re.finditer(assoc_pat, text_lower))
                for am in assoc_matches:
                    if not _is_negated(text_lower, am.start()):
                        assoc_str = am.group(0).strip()
                        if assoc_str not in matched_triggers:
                            matched_triggers.append(assoc_str)

    # General check for associated high-risk clinical factors when an emergency is detected
    if matched_categories:
        general_associated_patterns = [
            (r"\b(shortness\s+of\s+breath|difficulty\s+breathing|breathlessness)\b", "difficulty breathing"),
            (r"\b(dizziness|dizzy|lightheaded(ness)?)\b", "dizziness"),
            (r"\b(cold\s+sweat(s)?|profuse\s+sweating|diaphoresis)\b", "cold sweats"),
            (r"\b(nausea|vomiting)\b", "nausea")
        ]
        for pat, label in general_associated_patterns:
            m = re.search(pat, text_lower)
            if m and not _is_negated(text_lower, m.start()):
                matched_label = m.group(0).strip()
                if matched_label not in matched_triggers and label not in matched_triggers:
                    matched_triggers.append(matched_label)

    # Secondary check: High patient-reported severity (9 or 10) combined with acute high-risk keywords
    if not matched_categories and severity is not None and severity >= 9:
        high_risk_words = ["chest", "breathing", "heart", "head", "pain", "bleeding", "dizzy", "collapsed"]
        for hw in high_risk_words:
            if re.search(rf"\b{hw}\b", text_lower):
                matched_triggers.append(f"Severity rating {severity}/10 combined with acute symptom: {hw}")
                matched_categories.append("Acute Severe Symptom Presentation (Score >= 9)")
                primary_guidance = (
                    "URGENT ATTENTION: Patient-reported symptom severity is critically elevated (9-10/10). "
                    "Severe acute symptoms require immediate in-person emergency department evaluation. "
                    "Dial 112 or visit the nearest emergency room immediately."
                )
                break

    if matched_categories:
        category_display = " / ".join(matched_categories)
        return EmergencyDetectionResult(
            is_emergency=True,
            category=category_display,
            triggers=matched_triggers,
            urgency_code="EMERGENCY",
            guidance=primary_guidance
        )

    return EmergencyDetectionResult(
        is_emergency=False,
        urgency_code="NON_EMERGENCY"
    )
