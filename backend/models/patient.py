"""
Patient Profile, Medical Conditions, Allergies, and Patient Medications
"""
from datetime import datetime, date, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from backend.database import Base


def get_utc_now():
    return datetime.now(timezone.utc)


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(50), nullable=True)  # "Male", "Female", "Other", "Prefer not to say"
    blood_group = Column(String(10), nullable=True)  # "A+", "B+", "O+", "AB+", "A-", "B-", "O-", "AB-"
    height_cm = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)
    emergency_contact_name = Column(String(150), nullable=True)
    emergency_contact_phone = Column(String(50), nullable=True)
    emergency_contact_relation = Column(String(50), nullable=True)
    general_notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False)

    user = relationship("User", back_populates="profile")


class MedicalCondition(Base):
    __tablename__ = "medical_conditions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    condition_name = Column(String(200), nullable=False)
    diagnosed_date = Column(Date, nullable=True)
    status = Column(String(50), default="active", nullable=False)  # "active", "managed", "resolved"
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False)

    user = relationship("User", back_populates="medical_conditions")


class Allergy(Base):
    __tablename__ = "allergies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    allergen = Column(String(200), nullable=False)  # e.g., "Penicillin", "Peanuts", "Pollen"
    reaction = Column(String(200), nullable=False)  # e.g., "Hives", "Anaphylaxis", "Wheezing"
    severity = Column(String(50), default="mild", nullable=False)  # "mild", "moderate", "severe"
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)

    user = relationship("User", back_populates="allergies")


class PatientMedication(Base):
    """
    Patient-maintained medication list.
    STRICT NOTICE: Recorded for clinical context; system never prescribes or alters dosage.
    """
    __tablename__ = "patient_medications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    medication_name = Column(String(200), nullable=False)
    dosage = Column(String(100), nullable=False)  # e.g., "500 mg"
    frequency = Column(String(100), nullable=False)  # e.g., "Once daily in morning"
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_current = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)

    user = relationship("User", back_populates="medications")
