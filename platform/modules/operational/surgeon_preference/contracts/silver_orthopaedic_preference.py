from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime

class OrthopaedicPreference(BaseModel):
    surgeon_id: Optional[int] = Field(None, ge=1000, le=9999)
    surgeon_name: Optional[str]
    speciality: Literal["Orthopaedics"]
    subspeciality: Optional[
        Literal["Joints", "Trauma", "Spine", "Paediatric", "Foot And Ankle"]
    ]
    procedure: Optional[str]
    instrument: Optional[str]
    preferred_retractor_size: Optional[
        Literal["Small", "Medium", "Large", "Extra Large"]
    ]
    preferred_drill_brand: Optional[str]
    needs_backup_suction: Optional[bool]
    years_of_experience: Optional[int] = Field(None, ge=1, le=40)
    hospital_affiliation: Optional[str]
    generation_timestamp: Optional[datetime]
