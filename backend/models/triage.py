"""
Symptom Assessment and Structured Triage Models
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from backend.database import Base


def get_utc_now():
    return datetime.now(timezone.utc)


class SymptomAssessment(Base):
    __tablename__ = "symptom_assessments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)

    primary_symptom = Column(String(255), nullable=False)
    duration = Column(String(100), nullable=False)  # e.g., "3 days", "2 hours"
    severity = Column(Integer, nullable=False)  # 1 (mild) to 10 (unbearable)
    frequency = Column(String(100), nullable=True)  # "constant", "intermittent", "episodes"
    body_location = Column(String(150), nullable=True)  # "head", "chest", "throat", "abdomen"
    associated_symptoms = Column(Text, nullable=True)  # e.g., "nausea, dizziness, fever"
    relevant_history = Column(Text, nullable=True)  # e.g., "asthma, hypertension"
    raw_responses_json = Column(Text, nullable=True)  # JSON representation of full assessment flow
    created_at = Column(DateTime, default=get_utc_now, nullable=False)

    user = relationship("User", back_populates="symptom_assessments")
    conversation = relationship("Conversation", back_populates="symptom_assessments")
    triage_result = relationship("TriageResult", back_populates="assessment", uselist=False, cascade="all, delete-orphan")


class TriageResult(Base):
    """
    Structured urgency guidance result.
    Categories:
      - EMERGENCY: Immediate ER evaluation, dial 112
      - URGENT: Prompt clinical evaluation within hours
      - ROUTINE: Schedule standard clinic consultation
      - SELF_CARE: Home monitoring, supportive care & red flags
    """
    __tablename__ = "triage_results"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("symptom_assessments.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    urgency_level = Column(String(50), nullable=False)  # EMERGENCY | URGENT | ROUTINE | SELF_CARE
    guidance = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    emergency_flag = Column(Boolean, default=False, nullable=False)
    emergency_contacts = Column(String(255), default="Call 112 (National Emergency), 102/108 (Ambulance)")
    recommended_timeframe = Column(String(100), nullable=False)
    disclaimer = Column(
        Text,
        default="This preliminary triage is not a clinical diagnosis. In any medical emergency, seek in-person professional medical assistance immediately."
    )
    created_at = Column(DateTime, default=get_utc_now, nullable=False)

    assessment = relationship("SymptomAssessment", back_populates="triage_result")
