"""
Pydantic Schemas for Medicine Information Lookup
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class MedicineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    generic_name: str
    brand_names: Optional[str] = None
    drug_class: Optional[str] = None
    common_uses: str
    mechanism_of_action: Optional[str] = None
    common_side_effects: Optional[str] = None
    serious_warnings: Optional[str] = None
    precautions: Optional[str] = None
    contraindications: Optional[str] = None
    drug_interactions: Optional[str] = None
    source_reference: str
    source_url: Optional[str] = None
    last_reviewed_date: Optional[str] = None


class MedicineSearchResult(BaseModel):
    results: List[MedicineResponse]
    query: str
    total_found: int
    disclaimer: str = (
        "Medicine information is provided for educational and informational purposes only. "
        "Never adjust or stop prescribed medications without consulting your licensed physician."
    )
