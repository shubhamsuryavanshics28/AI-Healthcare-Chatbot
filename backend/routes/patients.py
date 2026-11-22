"""
Patient Profile, Medical History, Allergies, and Medication Management Routes
Strictly scopes all operations to current authenticated patient (RLS/Data Ownership).
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.patient import PatientProfile, MedicalCondition, Allergy, PatientMedication
from backend.models.chat import Conversation
from backend.models.triage import SymptomAssessment
from backend.schemas.patient import (
    PatientProfileUpdate,
    PatientProfileResponse,
    MedicalConditionCreate,
    MedicalConditionUpdate,
    MedicalConditionResponse,
    AllergyCreate,
    AllergyUpdate,
    AllergyResponse,
    PatientMedicationCreate,
    PatientMedicationUpdate,
    PatientMedicationResponse,
    PatientDashboardSummary
)
from backend.security.auth import get_current_user

router = APIRouter(prefix="/patients", tags=["Patient Records"])


# --- DASHBOARD ---
@router.get("/dashboard", response_model=PatientDashboardSummary)
def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return consolidated patient dashboard statistics and profile."""
    profile = db.query(PatientProfile).filter(PatientProfile.user_id == current_user.id).first()
    cond_count = db.query(MedicalCondition).filter(MedicalCondition.user_id == current_user.id).count()
    all_count = db.query(Allergy).filter(Allergy.user_id == current_user.id).count()
    med_count = db.query(PatientMedication).filter(PatientMedication.user_id == current_user.id).count()
    conv_count = db.query(Conversation).filter(Conversation.user_id == current_user.id).count()
    assess_count = db.query(SymptomAssessment).filter(SymptomAssessment.user_id == current_user.id).count()

    profile_resp = PatientProfileResponse.model_validate(profile) if profile else None

    return PatientDashboardSummary(
        profile=profile_resp,
        conditions_count=cond_count,
        allergies_count=all_count,
        medications_count=med_count,
        recent_assessments_count=assess_count,
        recent_conversations_count=conv_count
    )


# --- PATIENT PROFILE ---
@router.get("/profile", response_model=PatientProfileResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve or automatically initialize current patient profile."""
    profile = db.query(PatientProfile).filter(PatientProfile.user_id == current_user.id).first()
    if not profile:
        profile = PatientProfile(user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return PatientProfileResponse.model_validate(profile)


@router.put("/profile", response_model=PatientProfileResponse)
def update_profile(
    profile_in: PatientProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update patient demographic and physical measurements."""
    profile = db.query(PatientProfile).filter(PatientProfile.user_id == current_user.id).first()
    if not profile:
        profile = PatientProfile(user_id=current_user.id)
        db.add(profile)

    update_data = profile_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(profile, field, val)

    db.commit()
    db.refresh(profile)
    return PatientProfileResponse.model_validate(profile)


# --- MEDICAL CONDITIONS CRUD ---
@router.get("/medical-history", response_model=List[MedicalConditionResponse])
def get_medical_conditions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all medical conditions for the current patient."""
    records = db.query(MedicalCondition).filter(
        MedicalCondition.user_id == current_user.id
    ).order_by(MedicalCondition.created_at.desc()).all()
    return [MedicalConditionResponse.model_validate(r) for r in records]


@router.post("/medical-history", response_model=MedicalConditionResponse, status_code=status.HTTP_201_CREATED)
def create_medical_condition(
    condition_in: MedicalConditionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a new medical condition to the patient history."""
    rec = MedicalCondition(
        user_id=current_user.id,
        condition_name=condition_in.condition_name.strip(),
        diagnosed_date=condition_in.diagnosed_date,
        status=condition_in.status.strip().lower(),
        notes=condition_in.notes
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return MedicalConditionResponse.model_validate(rec)


@router.put("/medical-history/{condition_id}", response_model=MedicalConditionResponse)
def update_medical_condition(
    condition_id: int,
    condition_in: MedicalConditionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing medical condition record."""
    rec = db.query(MedicalCondition).filter(
        MedicalCondition.id == condition_id,
        MedicalCondition.user_id == current_user.id
    ).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical condition record not found or access unauthorized."
        )

    update_data = condition_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(rec, field, val)

    db.commit()
    db.refresh(rec)
    return MedicalConditionResponse.model_validate(rec)


@router.delete("/medical-history/{condition_id}")
def delete_medical_condition(
    condition_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a medical condition record."""
    rec = db.query(MedicalCondition).filter(
        MedicalCondition.id == condition_id,
        MedicalCondition.user_id == current_user.id
    ).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medical condition record not found or access unauthorized."
        )

    db.delete(rec)
    db.commit()
    return {"message": "Medical condition removed successfully", "id": condition_id}


# --- ALLERGIES CRUD ---
@router.get("/allergies", response_model=List[AllergyResponse])
def get_allergies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all allergies recorded for the current patient."""
    records = db.query(Allergy).filter(
        Allergy.user_id == current_user.id
    ).order_by(Allergy.created_at.desc()).all()
    return [AllergyResponse.model_validate(r) for r in records]


@router.post("/allergies", response_model=AllergyResponse, status_code=status.HTTP_201_CREATED)
def create_allergy(
    allergy_in: AllergyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Record a known patient allergy."""
    rec = Allergy(
        user_id=current_user.id,
        allergen=allergy_in.allergen.strip(),
        reaction=allergy_in.reaction.strip(),
        severity=allergy_in.severity.strip().lower(),
        notes=allergy_in.notes
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return AllergyResponse.model_validate(rec)


@router.put("/allergies/{allergy_id}", response_model=AllergyResponse)
def update_allergy(
    allergy_id: int,
    allergy_in: AllergyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing allergy record."""
    rec = db.query(Allergy).filter(
        Allergy.id == allergy_id,
        Allergy.user_id == current_user.id
    ).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allergy record not found or access unauthorized."
        )

    update_data = allergy_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(rec, field, val)

    db.commit()
    db.refresh(rec)
    return AllergyResponse.model_validate(rec)


@router.delete("/allergies/{allergy_id}")
def delete_allergy(
    allergy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an allergy record."""
    rec = db.query(Allergy).filter(
        Allergy.id == allergy_id,
        Allergy.user_id == current_user.id
    ).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allergy record not found or access unauthorized."
        )

    db.delete(rec)
    db.commit()
    return {"message": "Allergy record removed successfully", "id": allergy_id}


# --- PATIENT MEDICATIONS CRUD ---
@router.get("/medications", response_model=List[PatientMedicationResponse])
def get_patient_medications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all current and past medications logged by the patient."""
    records = db.query(PatientMedication).filter(
        PatientMedication.user_id == current_user.id
    ).order_by(PatientMedication.created_at.desc()).all()
    return [PatientMedicationResponse.model_validate(r) for r in records]


@router.post("/medications", response_model=PatientMedicationResponse, status_code=status.HTTP_201_CREATED)
def create_patient_medication(
    med_in: PatientMedicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Log an existing medication taken by the patient.
    Clinical notice: System only records patient-reported medications and never prescribes.
    """
    rec = PatientMedication(
        user_id=current_user.id,
        medication_name=med_in.medication_name.strip(),
        dosage=med_in.dosage.strip(),
        frequency=med_in.frequency.strip(),
        start_date=med_in.start_date,
        end_date=med_in.end_date,
        is_current=med_in.is_current,
        notes=med_in.notes
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return PatientMedicationResponse.model_validate(rec)


@router.put("/medications/{med_id}", response_model=PatientMedicationResponse)
def update_patient_medication(
    med_id: int,
    med_in: PatientMedicationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a patient medication entry."""
    rec = db.query(PatientMedication).filter(
        PatientMedication.id == med_id,
        PatientMedication.user_id == current_user.id
    ).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medication record not found or access unauthorized."
        )

    update_data = med_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(rec, field, val)

    db.commit()
    db.refresh(rec)
    return PatientMedicationResponse.model_validate(rec)


@router.delete("/medications/{med_id}")
def delete_patient_medication(
    med_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a medication entry."""
    rec = db.query(PatientMedication).filter(
        PatientMedication.id == med_id,
        PatientMedication.user_id == current_user.id
    ).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medication record not found or access unauthorized."
        )

    db.delete(rec)
    db.commit()
    return {"message": "Medication record removed successfully", "id": med_id}
