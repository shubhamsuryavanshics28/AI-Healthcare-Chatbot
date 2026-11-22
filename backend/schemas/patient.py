"""
Pydantic Schemas for Patient Profile, Conditions, Allergies, and Medications
"""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# --- Patient Profile ---
class PatientProfileBase(BaseModel):
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=50)
    blood_group: Optional[str] = Field(None, max_length=10)
    height_cm: Optional[float] = Field(None, ge=30, le=300)
    weight_kg: Optional[float] = Field(None, ge=1, le=500)
    emergency_contact_name: Optional[str] = Field(None, max_length=150)
    emergency_contact_phone: Optional[str] = Field(None, max_length=50)
    emergency_contact_relation: Optional[str] = Field(None, max_length=50)
    general_notes: Optional[str] = None


class PatientProfileUpdate(PatientProfileBase):
    pass


class PatientProfileResponse(PatientProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    updated_at: datetime


# --- Medical Conditions ---
class MedicalConditionBase(BaseModel):
    condition_name: str = Field(..., min_length=2, max_length=200)
    diagnosed_date: Optional[date] = None
    status: str = Field("active", max_length=50)  # active, managed, resolved
    notes: Optional[str] = None


class MedicalConditionCreate(MedicalConditionBase):
    pass


class MedicalConditionUpdate(BaseModel):
    condition_name: Optional[str] = Field(None, min_length=2, max_length=200)
    diagnosed_date: Optional[date] = None
    status: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class MedicalConditionResponse(MedicalConditionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


# --- Allergies ---
class AllergyBase(BaseModel):
    allergen: str = Field(..., min_length=2, max_length=200)
    reaction: str = Field(..., min_length=2, max_length=200)
    severity: str = Field("mild", max_length=50)  # mild, moderate, severe
    notes: Optional[str] = None


class AllergyCreate(AllergyBase):
    pass


class AllergyUpdate(BaseModel):
    allergen: Optional[str] = Field(None, min_length=2, max_length=200)
    reaction: Optional[str] = Field(None, min_length=2, max_length=200)
    severity: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class AllergyResponse(AllergyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime


# --- Patient Medications ---
class PatientMedicationBase(BaseModel):
    medication_name: str = Field(..., min_length=2, max_length=200)
    dosage: str = Field(..., min_length=1, max_length=100)
    frequency: str = Field(..., min_length=1, max_length=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: bool = True
    notes: Optional[str] = None


class PatientMedicationCreate(PatientMedicationBase):
    pass


class PatientMedicationUpdate(BaseModel):
    medication_name: Optional[str] = Field(None, min_length=2, max_length=200)
    dosage: Optional[str] = Field(None, min_length=1, max_length=100)
    frequency: Optional[str] = Field(None, min_length=1, max_length=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None
    notes: Optional[str] = None


class PatientMedicationResponse(PatientMedicationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime


# --- Dashboard Summary ---
class PatientDashboardSummary(BaseModel):
    profile: Optional[PatientProfileResponse] = None
    conditions_count: int
    allergies_count: int
    medications_count: int
    recent_assessments_count: int
    recent_conversations_count: int
