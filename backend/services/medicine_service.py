"""
Medicine Information Repository Service
Manages verified pharmaceutical reference data from official health authorities (FDA, MedlinePlus, CDSCO).
"""
import os
import json
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.models.medicine import MedicineInformation


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
MEDICINES_JSON_PATH = os.path.join(DATA_DIR, "medicines.json")


def seed_medicine_database(db: Session) -> int:
    """Populate database from medicines.json if empty."""
    existing_count = db.query(MedicineInformation).count()
    if existing_count > 0:
        return existing_count

    if not os.path.exists(MEDICINES_JSON_PATH):
        return 0

    with open(MEDICINES_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    added = 0
    for item in data:
        med = MedicineInformation(
            generic_name=item["generic_name"],
            brand_names=item.get("brand_names"),
            drug_class=item.get("drug_class"),
            common_uses=item["common_uses"],
            mechanism_of_action=item.get("mechanism_of_action"),
            common_side_effects=item.get("common_side_effects"),
            serious_warnings=item.get("serious_warnings"),
            precautions=item.get("precautions"),
            contraindications=item.get("contraindications"),
            drug_interactions=item.get("drug_interactions"),
            source_reference=item["source_reference"],
            source_url=item.get("source_url"),
            last_reviewed_date=item.get("last_reviewed_date")
        )
        db.add(med)
        added += 1

    db.commit()
    return added


def search_medicines(db: Session, query: str, limit: int = 10) -> List[MedicineInformation]:
    """
    Search medicine database by generic name, brand name, drug class, or common uses.
    """
    if not query or not query.strip():
        return db.query(MedicineInformation).limit(limit).all()

    search_term = f"%{query.strip()}%"
    results = db.query(MedicineInformation).filter(
        or_(
            MedicineInformation.generic_name.ilike(search_term),
            MedicineInformation.brand_names.ilike(search_term),
            MedicineInformation.drug_class.ilike(search_term),
            MedicineInformation.common_uses.ilike(search_term)
        )
    ).limit(limit).all()

    return results


def get_medicine_by_id(db: Session, medicine_id: int) -> Optional[MedicineInformation]:
    """Retrieve full medicine details by ID."""
    return db.query(MedicineInformation).filter(MedicineInformation.id == medicine_id).first()
