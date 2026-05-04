# schemas/orthopaedic_preference.py

from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime

class OrthopaedicPreference(BaseModel):
    surgeon_id: int = Field(..., ge=1000, le=9999)
    surgeon_name: str
    speciality: Literal["Orthopaedics"]
    subspecialty: Literal[
        "Joints", "Trauma", "Spine", "Paediatric", "Foot and Ankle"
    ]
    procedure: str
    instrument: str
    preferred_retractor_size: Literal["Small", "Medium", "Large", "Extra Large"]
    preferred_drill_brand: str
    needs_backup_suction: bool
    years_of_experience: int = Field(..., ge=1, le=40)
    hospital_affiliation: str
    generation_timestamp: datetime
