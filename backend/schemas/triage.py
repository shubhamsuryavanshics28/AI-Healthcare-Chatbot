"""
Pydantic Schemas for Symptom Assessment and Triage
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class SymptomAssessmentCreate(BaseModel):
    conversation_id: Optional[str] = None
    primary_symptom: str = Field(..., min_length=2, max_length=255)
    duration: str = Field(..., min_length=1, max_length=100)  # e.g., "3 days", "4 hours"
    severity: int = Field(..., ge=1, le=10, description="Severity scale 1 (mild) to 10 (emergency)")
    frequency: Optional[str] = Field("constant", max_length=100)
    body_location: Optional[str] = Field(None, max_length=150)
    associated_symptoms: Optional[str] = None
    relevant_history: Optional[str] = None


class TriageResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    urgency_level: str  # EMERGENCY, URGENT, ROUTINE, SELF_CARE
    guidance: str
    rationale: str
    emergency_flag: bool
    emergency_contacts: str
    recommended_timeframe: str
    disclaimer: str
    created_at: datetime


class SymptomAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    conversation_id: Optional[str] = None
    primary_symptom: str
    duration: str
    severity: int
    frequency: Optional[str] = None
    body_location: Optional[str] = None
    associated_symptoms: Optional[str] = None
    relevant_history: Optional[str] = None
    created_at: datetime
    triage_result: Optional[TriageResultResponse] = None
