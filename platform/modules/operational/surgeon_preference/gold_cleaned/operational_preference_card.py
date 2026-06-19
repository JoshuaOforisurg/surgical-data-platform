from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from config.paths import GOLD_DIR
from config.pipeline_version import DATA_PRODUCT_VERSION, GOLD_SCHEMA_VERSION
from contracts import OperationalPreferenceGold


class OperationalPreferenceGoldBuilder:
    """
    Builds the frontline-facing gold layer.

    This output is deliberately separate from analytics. It represents the
    current operational preference card that Streamlit can render for theatre
    staff, while preserving enriched validation metadata for review.
    """

    csv_filename = "gold_operational_preference_cards.csv"
    json_filename = "gold_operational_preference_cards.json"

    def __init__(self, output_dir: Path = GOLD_DIR):
        self.output_dir = Path(output_dir)

    def build(self, records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows = [self._record_to_row(record) for record in records]
        rows = self._latest_current_rows(rows)
        rows.sort(
            key=lambda row: (
                row.get("surgeon_name") or "",
                row.get("procedure") or "",
                row.get("preference_card_version") or row.get("version_number") or 0,
            )
        )
        return rows

    def write(self, rows: List[Dict[str, Any]]) -> Dict[str, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        csv_path = self.output_dir / self.csv_filename
        json_path = self.output_dir / self.json_filename

        if rows:
            with csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
        else:
            csv_path.write_text("", encoding="utf-8")

        json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

        return {"csv": csv_path, "json": json_path}

    def build_and_write(self, records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        rows = self.build(records)
        paths = self.write(rows)
        return {"rows": rows, "paths": paths}

    def _record_to_row(self, record: Dict[str, Any]) -> Dict[str, Any]:
        clinical_resolution = record.get("clinical_resolution") or {}
        derived_metadata = record.get("derived_metadata") or {}
        clinical_validation = record.get("clinical_validation") or {}
        enrichment_meta = record.get("_enrichment_meta") or {}
        quarantine_status = record.get("quarantine_status") or {}

        procedure = (
            clinical_resolution.get("procedure_name")
            or record.get("procedure_name")
            or "Unknown Procedure"
        )

        specialty = (
            derived_metadata.get("specialty")
            or record.get("surgeon_specialty")
            or record.get("specialty")
            or "Unknown"
        )

        instrument_system = clinical_resolution.get("system_name") or ""
        implant_system = clinical_resolution.get("implant_system") or "N/A"
        readiness_status = self._priority_from_validation(clinical_validation, quarantine_status)
        version_number = self._coerce_int(record.get("version_number")) or 1
        version_updated_at = self._clean_text(record.get("version_updated_at"))

        row = {
            "surgeon_id": self._clean_text(record.get("surgeon_id")),
            "preference_card_uid": self._preference_uid(
                record.get("surgeon_id"),
                record.get("surgeon_name"),
                clinical_resolution.get("procedure_id"),
                procedure,
            ),
            "preference_card_version": version_number,
            "preference_card_version_label": f"v{version_number}",
            "version_number": version_number,
            "version_updated_by": self._clean_text(record.get("version_updated_by")),
            "version_updated_at": version_updated_at,
            "is_current": True,
            "gold_schema_version": GOLD_SCHEMA_VERSION,
            "data_product_version": DATA_PRODUCT_VERSION,
            "surgeon_name": self._clean_text(record.get("surgeon_name")) or "Unknown Surgeon",
            "hospital": self._clean_text(record.get("hospital")) or "Local NHS Trust",
            "specialty": self._clean_text(specialty),
            "procedure": self._clean_text(procedure),
            "procedure_id": self._clean_text(clinical_resolution.get("procedure_id")),
            "procedure_code": self._json_list_to_text(record.get("procedure_codes")),
            "opcs_code": self._clean_text(clinical_resolution.get("opcs_code")),
            "diagnosis_code": self._json_list_to_text(record.get("diagnosis_codes")),
            "subspecialty": self._clean_text(
                derived_metadata.get("subspecialty") or record.get("procedure_subspecialty")
            ),
            "surgery_type": self._clean_text(
                derived_metadata.get("surgery_type") or record.get("procedure_surgery_type")
            ),
            "system_id": self._clean_text(clinical_resolution.get("system_id")),
            "instrument_system": self._clean_text(instrument_system) or "N/A",
            "implant_system": self._clean_text(implant_system),
            "manufacturer": self._clean_text(clinical_resolution.get("manufacturer")),
            "approach": self._clean_text(record.get("approach")) or "N/A",
            "instrument_set": self._items_summary(record.get("instruments")),
            "equipment": self._items_summary(record.get("equipment")),
            "draping": self._items_summary(record.get("draping")),
            "consumables": self._items_summary(record.get("consumables")),
            "disposables": self._items_summary(record.get("disposables")),
            "implants": self._items_summary(record.get("implants")),
            "sutures": self._items_summary(record.get("sutures")),
            "dressings": self._items_summary(record.get("dressings")),
            "instruments_json": self._items_json(record.get("instruments")),
            "equipment_json": self._items_json(record.get("equipment")),
            "draping_json": self._items_json(record.get("draping")),
            "consumables_json": self._items_json(record.get("consumables")),
            "disposables_json": self._items_json(record.get("disposables")),
            "implants_json": self._items_json(record.get("implants")),
            "sutures_json": self._items_json(record.get("sutures")),
            "dressings_json": self._items_json(record.get("dressings")),
            "positioning": self._clean_text(record.get("positioning_description")),
            "anaesthetic_notes": self._clean_text(record.get("anaesthetic_notes")),
            "skin_prep": self._clean_text(record.get("skin_prep_description")),
            "operating_theatre": self._clean_text(record.get("operating_theatre_description")),
            "special_instructions": self._clean_text(record.get("special_instructions_notes")),
            "laterality": self._clean_text(record.get("laterality")) or "N/A",
            "readiness_status": readiness_status,
            "priority_level": readiness_status,
            "validation_status": "QUARANTINED"
            if quarantine_status.get("is_corrupted")
            else enrichment_meta.get("status", "SUCCESS"),
            "validation_flags": json.dumps(clinical_validation.get("flags", [])),
            "missing_expected_items": json.dumps(
                clinical_validation.get("missing_expected_items", [])
            ),
            "confidence": enrichment_meta.get("confidence")
            or derived_metadata.get("confidence")
            or 0.0,
            "source_system": self._clean_text(record.get("source_system")),
            "gold_created_at": datetime.now(UTC).isoformat(),
        }
        return OperationalPreferenceGold(**row).model_dump(mode="json")

    def _latest_current_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        latest_by_card: Dict[tuple[str, str], Dict[str, Any]] = {}
        for row in rows:
            key = (
                self._clean_text(row.get("surgeon_name") or row.get("surgeon_id")).casefold(),
                self._clean_text(row.get("procedure_id") or row.get("procedure")).casefold(),
            )
            current = latest_by_card.get(key)
            if current is None or self._is_newer(row, current):
                latest_by_card[key] = row

        current_rows = list(latest_by_card.values())
        for row in current_rows:
            row["is_current"] = True
        return current_rows

    def _is_newer(self, candidate: Dict[str, Any], existing: Dict[str, Any]) -> bool:
        candidate_version = self._coerce_int(candidate.get("preference_card_version")) or 0
        existing_version = self._coerce_int(existing.get("preference_card_version")) or 0
        if candidate_version != existing_version:
            return candidate_version > existing_version

        candidate_timestamp = self._timestamp_sort_key(candidate)
        existing_timestamp = self._timestamp_sort_key(existing)
        if candidate_timestamp != existing_timestamp:
            return candidate_timestamp > existing_timestamp

        return float(candidate.get("confidence") or 0.0) > float(existing.get("confidence") or 0.0)

    def _timestamp_sort_key(self, row: Dict[str, Any]) -> datetime:
        return (
            self._parse_datetime(row.get("version_updated_at"))
            or self._parse_datetime(row.get("gold_created_at"))
            or datetime.min.replace(tzinfo=UTC)
        )

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            parsed = value
        else:
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    def _coerce_int(self, value: Any) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _preference_uid(
        self,
        surgeon_id: Any,
        surgeon_name: Any,
        procedure_id: Any,
        procedure: Any,
    ) -> str:
        identity = "|".join(
            [
                self._clean_text(surgeon_name) or self._clean_text(surgeon_id) or "unknown_surgeon",
                self._clean_text(procedure_id) or self._clean_text(procedure) or "unknown_procedure",
            ]
        ).casefold()
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]

    def _priority_from_validation(
        self,
        clinical_validation: Dict[str, Any],
        quarantine_status: Dict[str, Any],
    ) -> str:
        if quarantine_status.get("is_corrupted"):
            return "Review required"
        readiness = clinical_validation.get("readiness_status")
        if readiness:
            return readiness
        flags = clinical_validation.get("flags") or []
        missing = clinical_validation.get("missing_expected_items") or []
        if flags or missing:
            return "Check before use"
        return "Ready"

    def _items_summary(self, raw_items: Any) -> str:
        items = self._parse_items(raw_items)
        names = [self._item_name(item) for item in items]
        names = [name for name in names if name]
        return ", ".join(names) if names else "N/A"

    def _items_json(self, raw_items: Any) -> str:
        return json.dumps(self._parse_items(raw_items))

    def _json_list_to_text(self, value: Any) -> str:
        parsed = self._parse_items(value)
        if not parsed:
            return ""
        return ", ".join(str(item) for item in parsed if item)

    def _parse_items(self, value: Any) -> List[Any]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return [part.strip() for part in value.split(",") if part.strip()]
            return parsed if isinstance(parsed, list) else [parsed]
        return [value]

    def _item_name(self, item: Any) -> Optional[str]:
        if isinstance(item, dict):
            name = item.get("name") or item.get("item_name")
            quantity = item.get("quantity")
            if name and quantity not in (None, ""):
                return f"{name} (x{quantity})"
            return name
        return str(item) if item is not None else None

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).strip().split())
