"""
Medicine Information Repository Routes
Source-backed pharmaceutical reference search (FDA, MedlinePlus, CDSCO).
Strictly non-prescriptive and informational.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.schemas.medicine import MedicineResponse, MedicineSearchResult
from backend.security.auth import get_current_user
from backend.services.medicine_service import search_medicines, get_medicine_by_id

router = APIRouter(prefix="/medications", tags=["Medicine Information"])


@router.get("/search", response_model=MedicineSearchResult)
def search_medicine_repository(
    q: Optional[str] = Query(None, description="Search by generic name, brand name, class, or indication"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search curated medical reference database for medicine indications, warnings, side effects, and sources.
    """
    results = search_medicines(db, query=q or "", limit=limit)
    response_items = [MedicineResponse.model_validate(m) for m in results]

    return MedicineSearchResult(
        results=response_items,
        query=q or "",
        total_found=len(response_items)
    )


@router.get("/{medicine_id}", response_model=MedicineResponse)
def get_medicine_details(
    medicine_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve comprehensive pharmacological and safety details for a specific medicine.
    """
    medicine = get_medicine_by_id(db, medicine_id)
    if not medicine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medicine not found in curated knowledge base."
        )

    return MedicineResponse.model_validate(medicine)
