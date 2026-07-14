from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

MODULE_ROOT = Path(__file__).resolve().parents[2]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from config.paths import BRONZE_MANIFEST_DIR, SILVER_A_MANIFEST_DIR, SILVER_A_RECORDS_DIR
from contracts.silver_contracts import SilverARecord, SilverATableResult, SilverATransformResult


BOOL_FIELDS = {
    "approval_required",
    "barcode_enabled",
    "canonical_for_silver",
    "controlled_item",
    "emergency_order_available",
    "implantable",
    "reorder_required",
    "single_use",
    "sterile_required",
    "sterile_store",
}
INT_FIELDS = {
    "minimum_order_value_gbp",
    "par_level",
    "quantity",
    "quantity_available",
    "quantity_delta",
    "quantity_on_hand",
    "quantity_reserved",
    "qty_counted",
    "required_quantity",
    "source_profile_count",
    "standard_lead_time_days",
}
FLOAT_FIELDS = {"estimated_stock_value_gbp", "unit_cost_gbp"}
DATETIME_FIELDS = {"checked_at", "event_timestamp", "last_counted_at", "movement_at", "required_by_time", "scheduled_start"}
DATE_FIELDS = {"expiry_date"}

REQUIRED_FIELDS = {
    "erp_stock_balances": {"item_id", "location_id", "quantity_on_hand", "quantity_available"},
    "item_catalogue": {"item_id", "canonical_name", "item_type"},
    "manual_stocktake_spreadsheet": {"item_description", "qty_counted", "stock_area"},
    "scanner_stock_events": {"event_id", "item_id", "event_type", "event_timestamp"},
    "stock_locations": {"location_id", "location_name", "location_type"},
    "stock_lots": {"lot_id", "item_id", "location_id", "quantity_on_hand"},
    "stock_movements": {"movement_id", "item_id", "movement_type", "quantity", "movement_at"},
    "substitution_rules": {"substitution_rule_id", "preferred_item_id", "substitute_item_id"},
    "supplier_catalogue": {"supplier_id", "supplier_name"},
    "upcoming_case_demand": {"case_id", "item_id", "procedure_name", "required_quantity", "scheduled_start"},
}

FIELD_ALIASES = {
    "batch/lot": "batch_lot",
    "catalogue no": "catalogue_no",
    "checked at": "checked_at",
    "checked by": "checked_by",
    "expiry": "expiry",
    "hospital": "hospital",
    "item description": "item_description",
    "notes": "notes",
    "qty counted": "qty_counted",
    "shelf/bin": "shelf_bin",
    "stock area": "stock_area",
    "unit": "unit",
}


def latest_bronze_manifest(manifest_dir: Path = BRONZE_MANIFEST_DIR) -> Path:
    manifests = sorted(manifest_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not manifests:
        raise FileNotFoundError(f"No bronze manifests found in {manifest_dir}")
    return manifests[0]


def normalise_key(key: str) -> str:
    cleaned = " ".join(str(key).strip().split())
    alias = FIELD_ALIASES.get(cleaned.lower())
    if alias:
        return alias
    return "".join(char.lower() if char.isalnum() else "_" for char in cleaned).strip("_")


def empty_to_none(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "" or stripped.upper() in {"N/A", "NA", "NULL", "NONE"}:
            return None
        return stripped
    return value


def to_bool(value: Any) -> bool | None:
    value = empty_to_none(value)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "y"}:
        return True
    if lowered in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"cannot coerce {value!r} to bool")


def to_int(value: Any) -> int | None:
    value = empty_to_none(value)
    if value is None:
        return None
    return int(float(value))


def to_float(value: Any) -> float | None:
    value = empty_to_none(value)
    if value is None:
        return None
    return float(value)


def to_iso_datetime(value: Any) -> str | None:
    value = empty_to_none(value)
    if value is None:
        return None
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text).isoformat()


def to_iso_date(value: Any) -> str | None:
    value = empty_to_none(value)
    if value is None:
        return None
    return datetime.fromisoformat(str(value)).date().isoformat()


def coerce_value(field: str, value: Any) -> Any:
    value = empty_to_none(value)
    if field in BOOL_FIELDS:
        return to_bool(value)
    if field in INT_FIELDS:
        return to_int(value)
    if field in FLOAT_FIELDS:
        return to_float(value)
    if field in DATETIME_FIELDS:
        return to_iso_datetime(value)
    if field in DATE_FIELDS:
        return to_iso_date(value)
    return value


class SilverATransformer:
    def __init__(
        self,
        records_dir: Path = SILVER_A_RECORDS_DIR,
        manifest_dir: Path = SILVER_A_MANIFEST_DIR,
    ):
        self.records_dir = records_dir
        self.manifest_dir = manifest_dir

    def transform(self, bronze_manifest_path: Path) -> SilverATransformResult:
        bronze_manifest_path = Path(bronze_manifest_path)
        bronze_manifest = json.loads(bronze_manifest_path.read_text(encoding="utf-8"))
        run_id = str(bronze_manifest["run_id"])
        transformed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        run_records_dir = self.records_dir / run_id
        run_records_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

        table_outputs: list[dict[str, Any]] = []
        total_records = 0
        invalid_records = 0

        canonical_outputs = [
            output for output in bronze_manifest.get("record_outputs", [])
            if output.get("canonical_for_silver") is True
        ]
        if not canonical_outputs:
            raise ValueError(f"Bronze manifest has no canonical outputs: {bronze_manifest_path}")

        for output in canonical_outputs:
            dataset = str(output["dataset"])
            output_path = run_records_dir / f"{dataset}.jsonl"
            count, invalid_count = self._transform_table(
                dataset=dataset,
                bronze_record_path=Path(output["record_path"]),
                silver_output_path=output_path,
                transformed_at=transformed_at,
            )
            total_records += count
            invalid_records += invalid_count
            table_outputs.append(
                SilverATableResult(
                    dataset=dataset,
                    output_path=str(output_path),
                    records=count,
                    invalid_records=invalid_count,
                ).to_dict()
            )

        manifest_path = self.manifest_dir / f"{run_id}.json"
        result = SilverATransformResult(
            run_id=run_id,
            bronze_manifest_path=str(bronze_manifest_path),
            table_outputs=table_outputs,
            table_count=len(table_outputs),
            record_count=total_records,
            invalid_record_count=invalid_records,
            manifest_path=str(manifest_path),
        )
        manifest_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        return result

    def _transform_table(
        self,
        dataset: str,
        bronze_record_path: Path,
        silver_output_path: Path,
        transformed_at: str,
    ) -> tuple[int, int]:
        count = 0
        invalid_count = 0
        with bronze_record_path.open("r", encoding="utf-8") as bronze_file, silver_output_path.open(
            "w",
            encoding="utf-8",
        ) as silver_file:
            for line in bronze_file:
                if not line.strip():
                    continue
                count += 1
                bronze_record = json.loads(line)
                payload, errors = self.normalise_payload(dataset, bronze_record.get("raw_payload", {}))
                if errors:
                    invalid_count += 1
                silver_record = SilverARecord(
                    silver_record_id=f"silver_a:{bronze_record['record_id']}",
                    run_id=bronze_record["run_id"],
                    dataset=dataset,
                    source_record_id=bronze_record["record_id"],
                    source_file_id=bronze_record["source_file_id"],
                    source_checksum_sha256=bronze_record["source_checksum_sha256"],
                    source_row_number=int(bronze_record["source_row_number"]),
                    transformed_at=transformed_at,
                    validation_errors=errors,
                    payload=payload,
                )
                silver_file.write(json.dumps(silver_record.to_dict()) + "\n")
        return count, invalid_count

    def normalise_payload(self, dataset: str, raw_payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        payload: dict[str, Any] = {}
        errors: list[str] = []
        for key, value in raw_payload.items():
            field = normalise_key(key)
            try:
                payload[field] = coerce_value(field, value)
            except (TypeError, ValueError) as exc:
                payload[field] = empty_to_none(value)
                errors.append(f"{field}: {exc}")

        for field in sorted(REQUIRED_FIELDS.get(dataset, set())):
            if payload.get(field) in {None, ""}:
                errors.append(f"{field}: required")

        return payload, errors


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Transform canonical bronze stock inventory records to Silver A.")
    parser.add_argument(
        "--bronze-manifest",
        default=None,
        help="Bronze manifest path. Defaults to the latest manifest in data_lake/bronze/manifests.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    manifest_path = Path(args.bronze_manifest) if args.bronze_manifest else latest_bronze_manifest()
    result = SilverATransformer().transform(manifest_path)
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
