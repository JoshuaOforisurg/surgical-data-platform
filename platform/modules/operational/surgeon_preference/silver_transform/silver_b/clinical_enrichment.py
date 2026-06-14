from typing import Dict, Any, Optional, List
import json

from domain.clinical_reference_data import (
    CLINICAL_PROCEDURE_PROFILES,
    CLINICAL_INSTRUMENT_SYSTEMS,
    find_procedure_match,
    find_instrument_system_match,
    _normalise,
)


class ClinicalEnrichmentEngine:
    """
    Silver-B clinical enrichment layer.

    Responsibilities:
    - Parses Silver-A JSON strings safely.
    - Flags but preserves corrupted instrument quantities.
    - Resolves typos via fuzzy clinical lookup.
    """

    def __init__(self):
        pass

    def resolve_procedure(self, raw_text: str) -> Optional[str]:
        return find_procedure_match(raw_text)

    def resolve_instrument_system(self, raw_text: str) -> Optional[str]:
        return find_instrument_system_match(raw_text)

    def get_procedure_profile(self, procedure_id: str) -> Optional[dict]:
        return CLINICAL_PROCEDURE_PROFILES.get(procedure_id)

    def get_system_profile(self, system_id: str) -> Optional[dict]:
        return CLINICAL_INSTRUMENT_SYSTEMS.get(system_id)

    def normalize_items(self, items: Optional[List[str]]) -> set:
        if not items:
            return set()
        return {_normalise(item) for item in items if item and isinstance(item, str)}

    def item_is_present(self, expected_item: str, provided_items: set) -> bool:
        expected = _normalise(expected_item)
        if not expected:
            return True
        return any(
            expected == provided
            or expected in provided
            or provided in expected
            for provided in provided_items
        )

    def extract_and_audit_items(self, raw_json_str: Any, records_flags: List[str]) -> List[str]:
        """Unpacks JSON arrays, extracts names, and flags quantity corruptions."""
        if not raw_json_str:
            return []

        try:
            data = json.loads(raw_json_str) if isinstance(raw_json_str, str) else raw_json_str
            if not isinstance(data, list):
                return []

            clean_names = []
            for item in data:
                if isinstance(item, str):
                    clean_names.append(item)
                elif isinstance(item, dict):
                    qty = item.get("quantity")
                    name = item.get("name") or item.get("item_name")

                    # Flag the raw data anomaly instead of discarding the item
                    if qty in [-1, 999]:
                        records_flags.append(f"QUANTITY_ANOMALY_{str(name).upper().replace(' ', '_')}")

                    if name:
                        clean_names.append(name)
            return clean_names
        except Exception:
            return []

    def validate_compatibility(
            self,
            procedure_id: Optional[str],
            system_id: Optional[str],
            implants: Optional[List[str]] = None,
            instruments: Optional[List[str]] = None,
            equipment: Optional[List[str]] = None,
            inherited_flags: Optional[List[str]] = None
    ) -> Dict[str, Any]:

        flags = inherited_flags or []
        missing_items = []

        if not procedure_id:
            flags.append("PROCEDURE_NOT_RESOLVED")
            return {
                "valid": False,
                "readiness_status": "Review required",
                "flags": flags,
                "missing_expected_items": [],
                "confidence": 0.0,
            }

        proc = self.get_procedure_profile(procedure_id)
        system = self.get_system_profile(system_id) if system_id else None

        if not proc:
            flags.append("UNKNOWN_PROCEDURE")
            return {
                "valid": False,
                "readiness_status": "Review required",
                "flags": flags,
                "missing_expected_items": [],
                "confidence": 0.0,
            }

        expected_instruments = proc.get("expected_instruments", [])
        expected_implants = proc.get("expected_implants", [])
        expected_equipment = proc.get("expected_equipment", [])

        provided_instruments = self.normalize_items(instruments)
        provided_implants = self.normalize_items(implants)
        provided_equipment = self.normalize_items(equipment)

        missing_items.extend(
            sorted(
                item
                for item in expected_instruments
                if not self.item_is_present(item, provided_instruments)
            )
        )
        missing_items.extend(
            sorted(
                item
                for item in expected_implants
                if not self.item_is_present(item, provided_implants)
            )
        )
        missing_items.extend(
            sorted(
                item
                for item in expected_equipment
                if not self.item_is_present(item, provided_equipment)
            )
        )

        if system and procedure_id not in system.get("compatible_procedures", []):
            flags.append("SYSTEM_PROCEDURE_MISMATCH")

        has_critical_anomaly = any("QUANTITY_ANOMALY" in f for f in flags)
        has_mismatch = "SYSTEM_PROCEDURE_MISMATCH" in flags
        valid = not has_critical_anomaly and not has_mismatch and bool(procedure_id)
        if has_critical_anomaly or has_mismatch:
            readiness_status = "Review required"
        elif flags or missing_items:
            readiness_status = "Check before use"
        else:
            readiness_status = "Ready"

        return {
            "valid": valid,
            "readiness_status": readiness_status,
            "flags": flags,
            "missing_expected_items": missing_items,
        }

    def compute_confidence(self, procedure_id: Optional[str], validation_result: Dict[str, Any]) -> float:
        if not procedure_id:
            return 0.0

        score = 1.0
        flags = validation_result.get("flags", [])

        if "UNKNOWN_PROCEDURE" in flags: score -= 0.5
        if "SYSTEM_NOT_RESOLVED" in flags: score -= 0.1
        if "SYSTEM_PROCEDURE_MISMATCH" in flags: score -= 0.2
        if any("QUANTITY_ANOMALY" in f for f in flags): score -= 0.15

        missing_count = len(validation_result.get("missing_expected_items", []))
        score -= min(0.2, missing_count * 0.03)

        return max(0.0, round(score, 3))

    def enrich(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Main clinical lookup and validation pipeline."""
        pipeline_flags = []

        raw_procedure = record.get("procedure_name") or ""

        procedure_id = self.resolve_procedure(raw_procedure)
        proc_profile = self.get_procedure_profile(procedure_id) if procedure_id else None

        # Extract names and capture anomalies in pipeline_flags
        clean_instruments = self.extract_and_audit_items(record.get("instruments"), pipeline_flags)
        clean_implants = self.extract_and_audit_items(record.get("implants"), pipeline_flags)
        clean_equipment = self.extract_and_audit_items(record.get("equipment"), pipeline_flags)

        system_lookup_text = " ".join(
            str(value or "")
            for value in [
                record.get("instrument_system"),
                record.get("implant_system"),
                " ".join(clean_instruments),
                " ".join(clean_implants),
                " ".join(clean_equipment),
            ]
        )
        system_id = self.resolve_instrument_system(system_lookup_text)
        if not system_id and proc_profile:
            configured_systems = proc_profile.get("instrument_systems") or []
            system_id = configured_systems[0] if configured_systems else None

        system_profile = self.get_system_profile(system_id) if system_id else None
        if not system_id and procedure_id:
            pipeline_flags.append("SYSTEM_NOT_RESOLVED")

        validation = self.validate_compatibility(
            procedure_id=procedure_id,
            system_id=system_id,
            implants=clean_implants,
            instruments=clean_instruments,
            equipment=clean_equipment,
            inherited_flags=pipeline_flags
        )

        confidence = self.compute_confidence(procedure_id=procedure_id, validation_result=validation)
        validation["confidence"] = confidence

        # Inject quarantine trigger metadata
        is_quarantine_target = any("QUANTITY_ANOMALY" in f for f in validation["flags"])

        return {
            **record,
            "quarantine_status": {
                "is_corrupted": is_quarantine_target,
                "quarantine_reason": "CRITICAL_QUANTITY_ANOMALY" if is_quarantine_target else None
            },
            "clinical_resolution": {
                "procedure_id": procedure_id,
                "procedure_name": proc_profile.get("name") if proc_profile else None,
                "system_id": system_id,
                "system_name": system_profile.get("name") if system_profile else None,
                "manufacturer": system_profile.get("manufacturer") if system_profile else None,
                "implant_system": proc_profile.get("implant_system") if proc_profile else None,
                "opcs_code": proc_profile.get("opcs_code") if proc_profile else None,
            },
            "derived_metadata": {
                "specialty": proc_profile.get("specialty") if proc_profile else None,
                "subspecialty": proc_profile.get("subspecialty") if proc_profile else None,
                "surgery_type": proc_profile.get("surgery_type") if proc_profile else None,
                "confidence": confidence,
            },
            "clinical_validation": validation,
        }
