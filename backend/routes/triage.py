"""
Symptom Assessment and Triage Routes
Provides clinical urgency categorization, emergency detection escalation, and assessment history.
"""
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.triage import SymptomAssessment, TriageResult
from backend.schemas.triage import (
    SymptomAssessmentCreate,
    SymptomAssessmentResponse,
    TriageResultResponse
)
from backend.security.auth import get_current_user
from backend.services.triage_service import evaluate_triage

router = APIRouter(prefix="/triage", tags=["Symptom Assessment & Triage"])


def _format_assessment_response(assessment: SymptomAssessment) -> SymptomAssessmentResponse:
    triage_res = None
    if assessment.triage_result:
        triage_res = TriageResultResponse.model_validate(assessment.triage_result)

    return SymptomAssessmentResponse(
        id=assessment.id,
        user_id=assessment.user_id,
        conversation_id=assessment.conversation_id,
        primary_symptom=assessment.primary_symptom,
        duration=assessment.duration,
        severity=assessment.severity,
        frequency=assessment.frequency,
        body_location=assessment.body_location,
        associated_symptoms=assessment.associated_symptoms,
        relevant_history=assessment.relevant_history,
        created_at=assessment.created_at,
        triage_result=triage_res
    )


@router.post("/assess", response_model=SymptomAssessmentResponse, status_code=status.HTTP_201_CREATED)
def submit_symptom_assessment(
    assessment_in: SymptomAssessmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit structured patient symptoms for clinical triage evaluation.
    Guarantees independent emergency rule evaluation before any urgency category is assigned.
    """
    # Evaluate triage category using clinical rule engine
    eval_result = evaluate_triage(
        primary_symptom=assessment_in.primary_symptom,
        duration=assessment_in.duration,
        severity=assessment_in.severity,
        frequency=assessment_in.frequency,
        body_location=assessment_in.body_location,
        associated_symptoms=assessment_in.associated_symptoms,
        relevant_history=assessment_in.relevant_history
    )

    # Persist SymptomAssessment
    assessment_db = SymptomAssessment(
        user_id=current_user.id,
        conversation_id=assessment_in.conversation_id,
        primary_symptom=assessment_in.primary_symptom.strip(),
        duration=assessment_in.duration.strip(),
        severity=assessment_in.severity,
        frequency=assessment_in.frequency,
        body_location=assessment_in.body_location,
        associated_symptoms=assessment_in.associated_symptoms,
        relevant_history=assessment_in.relevant_history,
        raw_responses_json=json.dumps(assessment_in.model_dump())
    )
    db.add(assessment_db)
    db.flush()

    # Persist TriageResult
    triage_db = TriageResult(
        assessment_id=assessment_db.id,
        urgency_level=eval_result.urgency_level,
        guidance=eval_result.guidance,
        rationale=eval_result.rationale,
        emergency_flag=eval_result.emergency_flag,
        recommended_timeframe=eval_result.recommended_timeframe,
        disclaimer=eval_result.disclaimer
    )
    db.add(triage_db)
    db.commit()
    db.refresh(assessment_db)

    return _format_assessment_response(assessment_db)


@router.get("/history", response_model=List[SymptomAssessmentResponse])
def get_assessment_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve full chronological assessment history for authenticated patient."""
    records = db.query(SymptomAssessment).filter(
        SymptomAssessment.user_id == current_user.id
    ).order_by(SymptomAssessment.created_at.desc()).all()

    return [_format_assessment_response(r) for r in records]


@router.get("/history/{assessment_id}", response_model=SymptomAssessmentResponse)
def get_assessment_detail(
    assessment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve details for a specific symptom assessment."""
    rec = db.query(SymptomAssessment).filter(
        SymptomAssessment.id == assessment_id,
        SymptomAssessment.user_id == current_user.id
    ).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment record not found or access unauthorized."
        )

    return _format_assessment_response(rec)
