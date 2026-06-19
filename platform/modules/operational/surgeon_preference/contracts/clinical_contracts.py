from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from config.pipeline_version import GOLD_SCHEMA_VERSION, SILVER_SCHEMA_VERSION


class BronzeFileMetadata(BaseModel):
    run_id: str
    bucket: str
    object_key: str
    object_uri: str
    original_filename: str
    file_extension: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    checksum_sha256: Optional[str] = None


class ClinicalItem(BaseModel):
    name: str
    quantity: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.strip().split())
        if not value:
            raise ValueError("clinical item name cannot be blank")
        return value


class SilverClinicalRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    surgeon_id: Optional[str] = None
    surgeon_name: Optional[str] = None
    surgeon_specialty: Optional[str] = None
    procedure_name: Optional[str] = None
    procedure_codes: List[str] = Field(default_factory=list)
    diagnosis_codes: List[str] = Field(default_factory=list)
    procedure_subspecialty: Optional[str] = None
    procedure_surgery_type: Optional[str] = None
    instrument_system: Optional[str] = None
    implant_system: Optional[str] = None
    instruments: List[ClinicalItem] = Field(default_factory=list)
    equipment: List[ClinicalItem] = Field(default_factory=list)
    consumables: List[ClinicalItem] = Field(default_factory=list)
    disposables: List[ClinicalItem] = Field(default_factory=list)
    implants: List[ClinicalItem] = Field(default_factory=list)
    sutures: List[ClinicalItem] = Field(default_factory=list)
    dressings: List[ClinicalItem] = Field(default_factory=list)
    positioning_description: Optional[str] = None
    anaesthetic_notes: Optional[str] = None
    skin_prep_description: Optional[str] = None
    operating_theatre_description: Optional[str] = None
    special_instructions_notes: Optional[str] = None
    version_number: Optional[int] = None
    version_updated_by: Optional[str] = None
    version_updated_at: Optional[datetime | str] = None
    source_system: Optional[str] = None
    processed_at: Optional[datetime | str] = None
    pipeline_version: str = SILVER_SCHEMA_VERSION


class ClinicalValidationResult(BaseModel):
    valid: bool
    readiness_status: Literal["Ready", "Check before use", "Review required"]
    flags: List[str] = Field(default_factory=list)
    missing_expected_items: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class OperationalPreferenceGold(BaseModel):
    model_config = ConfigDict(extra="allow")

    surgeon_id: Optional[str] = None
    preference_card_uid: Optional[str] = None
    preference_card_version: Optional[int] = None
    preference_card_version_label: Optional[str] = None
    version_number: Optional[int] = None
    version_updated_by: Optional[str] = None
    version_updated_at: Optional[datetime | str] = None
    is_current: bool = True
    gold_schema_version: str = GOLD_SCHEMA_VERSION
    data_product_version: Optional[str] = None
    surgeon_name: str
    hospital: str
    specialty: str
    procedure: str
    procedure_id: Optional[str] = None
    procedure_code: Optional[str] = None
    diagnosis_code: Optional[str] = None
    subspecialty: Optional[str] = None
    surgery_type: Optional[str] = None
    implant_system: Optional[str] = None
    instrument_set: str
    equipment: Optional[str] = None
    draping: Optional[str] = None
    consumables: Optional[str] = None
    disposables: Optional[str] = None
    implants: Optional[str] = None
    sutures: Optional[str] = None
    dressings: Optional[str] = None
    positioning: Optional[str] = None
    anaesthetic_notes: Optional[str] = None
    skin_prep: Optional[str] = None
    special_instructions: Optional[str] = None
    priority_level: Literal["Ready", "Check before use", "Review required"]
    validation_status: str
    validation_flags: str
    missing_expected_items: str
    confidence: float = Field(ge=0.0, le=1.0)
    gold_created_at: datetime | str


class GoldAnalyticsSnapshot(BaseModel):
    source_record_count: int = 0
    surgeon_summary: Dict[str, Any]
    procedure_usage: Dict[str, int]
    system_usage: Dict[str, int]
    missing_items: Dict[str, int]
    system_mismatch_rate: float
    confidence_profile: Dict[str, Any]
