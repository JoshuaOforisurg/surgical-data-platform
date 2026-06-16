from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from domain.clinical_reference_data import (
    CLINICAL_INSTRUMENT_SYSTEMS,
    CLINICAL_PROCEDURE_PROFILES,
    find_instrument_system_match,
    find_procedure_match,
    normalise_special_instruction,
    _match_score,
)


class ProcedureReference(BaseModel):
    procedure_id: str
    name: str
    specialty: str
    subspecialty: str
    surgery_type: str
    opcs_code: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    instrument_systems: List[str] = Field(default_factory=list)
    implant_system: Optional[str] = None
    manufacturer: Optional[str] = None


class InstrumentSystemReference(BaseModel):
    system_id: str
    name: str
    manufacturer: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    compatible_procedures: List[str] = Field(default_factory=list)
    compatible_implants: List[str] = Field(default_factory=list)


class SupplyProfileReference(BaseModel):
    procedure_id: str
    expected_draping: List[str] = Field(default_factory=list)
    expected_consumables: List[str] = Field(default_factory=list)
    expected_disposables: List[str] = Field(default_factory=list)
    expected_sutures: List[str] = Field(default_factory=list)
    expected_dressings: List[str] = Field(default_factory=list)


class OperationalMetadataReference(BaseModel):
    procedure_id: str
    expected_positioning: List[str] = Field(default_factory=list)
    expected_anaesthetic: List[str] = Field(default_factory=list)
    expected_skin_prep: List[str] = Field(default_factory=list)
    theatre_environment: str
    case_complexity: Optional[str] = None
    expected_duration_minutes: Optional[int] = None
    turnaround_minutes: Optional[int] = None
    laterality_required: bool = True
    imaging_required: bool = False
    requires_ultra_clean_air: bool = False
    implant_representative_required: bool = False
    loan_kit_lead_time_days: int = 0
    blood_product_group_and_save: bool = False
    antibiotic_window_minutes: Optional[int] = None
    critical_checks: List[str] = Field(default_factory=list)


class ClinicalReferenceService:
    """
    Normalized facade over the in-repo clinical catalogue.

    The current backing store is Python reference data. The method contracts are
    table-shaped on purpose so Postgres, Iceberg, or an API can replace the
    backing store later without changing Silver-B enrichment.
    """

    @lru_cache(maxsize=1)
    def procedure_table(self) -> tuple[ProcedureReference, ...]:
        return tuple(
            ProcedureReference(
                procedure_id=procedure_id,
                name=profile["name"],
                specialty=profile["specialty"],
                subspecialty=profile["subspecialty"],
                surgery_type=profile["surgery_type"],
                opcs_code=profile.get("opcs_code"),
                aliases=profile.get("aliases", []),
                instrument_systems=profile.get("instrument_systems", []),
                implant_system=profile.get("implant_system"),
                manufacturer=profile.get("manufacturer"),
            )
            for procedure_id, profile in CLINICAL_PROCEDURE_PROFILES.items()
        )

    @lru_cache(maxsize=1)
    def instrument_system_table(self) -> tuple[InstrumentSystemReference, ...]:
        return tuple(
            InstrumentSystemReference(
                system_id=system_id,
                name=system["name"],
                manufacturer=system.get("manufacturer"),
                aliases=system.get("aliases", []),
                compatible_procedures=system.get("compatible_procedures", []),
                compatible_implants=system.get("compatible_implants", []),
            )
            for system_id, system in CLINICAL_INSTRUMENT_SYSTEMS.items()
        )

    @lru_cache(maxsize=1)
    def supply_profile_table(self) -> tuple[SupplyProfileReference, ...]:
        return tuple(
            SupplyProfileReference(
                procedure_id=procedure_id,
                expected_draping=profile.get("expected_draping", []),
                expected_consumables=profile.get("expected_consumables", []),
                expected_disposables=profile.get("expected_disposables", []),
                expected_sutures=profile.get("expected_sutures", []),
                expected_dressings=profile.get("expected_dressings", []),
            )
            for procedure_id, profile in CLINICAL_PROCEDURE_PROFILES.items()
        )

    @lru_cache(maxsize=1)
    def operational_metadata_table(self) -> tuple[OperationalMetadataReference, ...]:
        return tuple(
            OperationalMetadataReference(
                procedure_id=procedure_id,
                expected_positioning=profile.get("expected_positioning", []),
                expected_anaesthetic=profile.get("expected_anaesthetic", []),
                expected_skin_prep=profile.get("expected_skin_prep", []),
                theatre_environment=profile.get("theatre_environment", "Standard elective theatre"),
                case_complexity=profile.get("case_complexity"),
                expected_duration_minutes=profile.get("expected_duration_minutes"),
                turnaround_minutes=profile.get("turnaround_minutes"),
                laterality_required=profile.get("laterality_required", True),
                imaging_required=profile.get("imaging_required", False),
                requires_ultra_clean_air=profile.get("requires_ultra_clean_air", False),
                implant_representative_required=profile.get("implant_representative_required", False),
                loan_kit_lead_time_days=profile.get("loan_kit_lead_time_days", 0),
                blood_product_group_and_save=profile.get("blood_product_group_and_save", False),
                antibiotic_window_minutes=profile.get("antibiotic_window_minutes"),
                critical_checks=profile.get("critical_checks", []),
            )
            for procedure_id, profile in CLINICAL_PROCEDURE_PROFILES.items()
        )

    def resolve_procedure(self, raw_text: str) -> Optional[str]:
        return find_procedure_match(raw_text)

    def resolve_instrument_system(self, raw_text: str) -> Optional[str]:
        return find_instrument_system_match(raw_text)

    def normalise_instruction(self, raw_text: Optional[str]) -> Optional[str]:
        return normalise_special_instruction(raw_text)

    def instructions_for_procedure(self, procedure_id: Optional[str]) -> List[str]:
        profile = self.get_procedure_profile(procedure_id)
        if not profile:
            return []
        return profile.get("expected_special_instructions", [])

    def normalise_instruction_for_procedure(
        self,
        raw_text: Optional[str],
        procedure_id: Optional[str],
    ) -> Optional[str]:
        procedure_instructions = self.instructions_for_procedure(procedure_id)
        if not raw_text:
            return procedure_instructions[0] if procedure_instructions else None

        if not procedure_instructions:
            return self.normalise_instruction(raw_text)

        best_instruction = None
        best_score = 0.0
        for instruction in procedure_instructions:
            score = _match_score(raw_text, instruction, threshold=0.55)
            if score > best_score:
                best_instruction = instruction
                best_score = score

        if best_instruction and best_score >= 0.55:
            return best_instruction

        generic_instruction = self.normalise_instruction(raw_text)
        if generic_instruction in procedure_instructions:
            return generic_instruction
        return procedure_instructions[0]

    def get_procedure_profile(self, procedure_id: Optional[str]) -> Optional[dict]:
        if not procedure_id:
            return None
        return CLINICAL_PROCEDURE_PROFILES.get(procedure_id)

    def get_instrument_system_profile(self, system_id: Optional[str]) -> Optional[dict]:
        if not system_id:
            return None
        return CLINICAL_INSTRUMENT_SYSTEMS.get(system_id)

    def validate_catalogue(self) -> Dict[str, Any]:
        missing_systems = []
        invalid_system_links = []
        missing_supply_profiles = []
        missing_operational_metadata = []

        for procedure_id, profile in CLINICAL_PROCEDURE_PROFILES.items():
            systems = profile.get("instrument_systems", [])
            if not systems:
                missing_systems.append(procedure_id)
            for system_id in systems:
                system = CLINICAL_INSTRUMENT_SYSTEMS.get(system_id)
                if not system:
                    invalid_system_links.append({"procedure_id": procedure_id, "system_id": system_id})
                elif procedure_id not in system.get("compatible_procedures", []):
                    invalid_system_links.append({"procedure_id": procedure_id, "system_id": system_id})

            expected_supply_keys = [
                "expected_draping",
                "expected_consumables",
                "expected_disposables",
                "expected_sutures",
                "expected_dressings",
                "expected_special_instructions",
            ]
            if any(not profile.get(key) for key in expected_supply_keys):
                missing_supply_profiles.append(procedure_id)

            expected_operational_keys = [
                "expected_positioning",
                "expected_anaesthetic",
                "expected_skin_prep",
                "theatre_environment",
                "case_complexity",
                "expected_duration_minutes",
                "turnaround_minutes",
                "critical_checks",
            ]
            if any(profile.get(key) in (None, "", []) for key in expected_operational_keys):
                missing_operational_metadata.append(procedure_id)

        return {
            "valid": not missing_systems
            and not invalid_system_links
            and not missing_supply_profiles
            and not missing_operational_metadata,
            "procedure_count": len(CLINICAL_PROCEDURE_PROFILES),
            "instrument_system_count": len(CLINICAL_INSTRUMENT_SYSTEMS),
            "missing_systems": missing_systems,
            "invalid_system_links": invalid_system_links,
            "missing_supply_profiles": missing_supply_profiles,
            "missing_operational_metadata": missing_operational_metadata,
        }
