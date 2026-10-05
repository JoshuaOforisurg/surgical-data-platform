from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from config.pipeline_version import (
    SILVER_SCHEMA_VERSION,
    SILVER_TO_GOLD_CONTRACT_VERSION,
)
from contracts.clinical_contracts import ClinicalValidationResult


class ContractViolationError(ValueError):
    """Raised when records do not satisfy a published pipeline boundary."""


class ClinicalResolution(BaseModel):
    model_config = ConfigDict(extra="allow")

    procedure_id: Optional[str] = None
    procedure_name: Optional[str] = None
    system_id: Optional[str] = None
    system_name: Optional[str] = None


class QuarantineStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    is_corrupted: bool
    quarantine_reason: Optional[str] = None


class EnrichmentMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Literal["SUCCESS", "QUARANTINED", "FAILED"]
    confidence: float = Field(ge=0.0, le=1.0)


class SilverToGoldRecord(BaseModel):
    """Versioned contract accepted by the operational Gold builders."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    pipeline_version: str
    surgeon_name: str = Field(min_length=1)
    procedure_name: str = Field(min_length=1)
    clinical_resolution: ClinicalResolution
    clinical_validation: ClinicalValidationResult
    quarantine_status: QuarantineStatus
    enrichment_metadata: EnrichmentMetadata = Field(alias="_enrichment_meta")
    instruments: List[Any] = Field(default_factory=list)
    equipment: List[Any] = Field(default_factory=list)
    consumables: List[Any] = Field(default_factory=list)
    disposables: List[Any] = Field(default_factory=list)
    implants: List[Any] = Field(default_factory=list)
    sutures: List[Any] = Field(default_factory=list)
    dressings: List[Any] = Field(default_factory=list)

    @field_validator("pipeline_version")
    @classmethod
    def require_supported_silver_schema(cls, value: str) -> str:
        if value != SILVER_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Silver schema {value!r}; expected {SILVER_SCHEMA_VERSION!r}"
            )
        return value

    @field_validator(
        "instruments",
        "equipment",
        "consumables",
        "disposables",
        "implants",
        "sutures",
        "dressings",
        mode="before",
    )
    @classmethod
    def parse_item_collection(cls, value: Any) -> List[Any]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("item collection must contain valid JSON") from exc
        if not isinstance(value, list):
            raise ValueError("item collection must be a list")
        return value


def validate_silver_to_gold_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not records:
        raise ContractViolationError("Silver-to-Gold contract received no records.")

    for index, record in enumerate(records):
        try:
            SilverToGoldRecord.model_validate(record)
        except ValidationError as exc:
            raise ContractViolationError(
                f"Silver-to-Gold contract failed for record {index}: {exc}"
            ) from exc

    return {
        "contract_version": SILVER_TO_GOLD_CONTRACT_VERSION,
        "silver_schema_version": SILVER_SCHEMA_VERSION,
        "records_validated": len(records),
        "passed": True,
    }
