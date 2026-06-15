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

    def resolve_procedure(self, raw_text: str) -> Optional[str]:
        return find_procedure_match(raw_text)

    def resolve_instrument_system(self, raw_text: str) -> Optional[str]:
        return find_instrument_system_match(raw_text)

    def normalise_instruction(self, raw_text: Optional[str]) -> Optional[str]:
        return normalise_special_instruction(raw_text)

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
            ]
            if any(not profile.get(key) for key in expected_supply_keys):
                missing_supply_profiles.append(procedure_id)

        return {
            "valid": not missing_systems and not invalid_system_links and not missing_supply_profiles,
            "procedure_count": len(CLINICAL_PROCEDURE_PROFILES),
            "instrument_system_count": len(CLINICAL_INSTRUMENT_SYSTEMS),
            "missing_systems": missing_systems,
            "invalid_system_links": invalid_system_links,
            "missing_supply_profiles": missing_supply_profiles,
        }
