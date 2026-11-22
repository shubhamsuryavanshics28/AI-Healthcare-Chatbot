"""
Medicine Information Repository Model
Backed by verified, trusted medical reference sources (FDA, MedlinePlus, CDSCO).
Strictly non-prescriptive informational resource.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from backend.database import Base


def get_utc_now():
    return datetime.now(timezone.utc)


class MedicineInformation(Base):
    __tablename__ = "medicine_information"

    id = Column(Integer, primary_key=True, index=True)
    generic_name = Column(String(200), unique=True, index=True, nullable=False)
    brand_names = Column(String(500), nullable=True)  # Comma-separated common brand names
    drug_class = Column(String(200), nullable=True)
    common_uses = Column(Text, nullable=False)
    mechanism_of_action = Column(Text, nullable=True)
    common_side_effects = Column(Text, nullable=True)
    serious_warnings = Column(Text, nullable=True)
    precautions = Column(Text, nullable=True)
    contraindications = Column(Text, nullable=True)
    drug_interactions = Column(Text, nullable=True)
    source_reference = Column(String(255), nullable=False)  # e.g., "MedlinePlus / US FDA"
    source_url = Column(String(500), nullable=True)
    last_reviewed_date = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
