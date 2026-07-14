from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

MODULE_ROOT = Path(__file__).resolve().parents[2]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from config.paths import SILVER_A_MANIFEST_DIR, SILVER_B_MANIFEST_DIR, SILVER_B_RECORDS_DIR
from contracts.silver_contracts import SilverBTableResult, SilverBTransformResult


def latest_silver_a_manifest(manifest_dir: Path = SILVER_A_MANIFEST_DIR) -> Path:
    manifests = sorted(manifest_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not manifests:
        raise FileNotFoundError(f"No Silver A manifests found in {manifest_dir}")
    return manifests[0]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def payloads_by_dataset(silver_a_manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    datasets: dict[str, list[dict[str, Any]]] = {}
    for output in silver_a_manifest.get("table_outputs", []):
        dataset = output["dataset"]
        records = read_jsonl(Path(output["output_path"]))
        datasets[dataset] = [record["payload"] for record in records if not record.get("validation_errors")]
    return datasets


def parse_date(value: Any) -> date | None:
    if value in {None, ""}:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def days_until(value: Any, today: date) -> int | None:
    parsed = parse_date(value)
    if parsed is None:
        return None
    return (parsed - today).days


class SilverBTransformer:
    def __init__(
        self,
        records_dir: Path = SILVER_B_RECORDS_DIR,
        manifest_dir: Path = SILVER_B_MANIFEST_DIR,
    ):
        self.records_dir = records_dir
        self.manifest_dir = manifest_dir

    def transform(self, silver_a_manifest_path: Path) -> SilverBTransformResult:
        silver_a_manifest_path = Path(silver_a_manifest_path)
        silver_a_manifest = json.loads(silver_a_manifest_path.read_text(encoding="utf-8"))
        run_id = str(silver_a_manifest["run_id"])
        datasets = payloads_by_dataset(silver_a_manifest)
        today = datetime.now(timezone.utc).date()

        run_records_dir = self.records_dir / run_id
        run_records_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

        item_lookup = {item["item_id"]: item for item in datasets.get("item_catalogue", [])}
        location_lookup = {location["location_id"]: location for location in datasets.get("stock_locations", [])}
        erp_lookup = {
            (balance["item_id"], balance["location_id"]): balance
            for balance in datasets.get("erp_stock_balances", [])
        }
        stock_positions = self.build_stock_positions(
            stock_lots=datasets.get("stock_lots", []),
            item_lookup=item_lookup,
            location_lookup=location_lookup,
            erp_lookup=erp_lookup,
            today=today,
        )
        case_readiness = self.build_case_readiness(
            demand_rows=datasets.get("upcoming_case_demand", []),
            stock_positions=stock_positions,
            substitution_rules=datasets.get("substitution_rules", []),
        )

        outputs = {
            "stock_positions": stock_positions,
            "case_readiness": case_readiness,
        }

        table_outputs: list[dict[str, Any]] = []
        total_records = 0
        for dataset, rows in outputs.items():
            output_path = run_records_dir / f"{dataset}.jsonl"
            self.write_jsonl(output_path, rows)
            total_records += len(rows)
            table_outputs.append(
                SilverBTableResult(
                    dataset=dataset,
                    output_path=str(output_path),
                    records=len(rows),
                ).to_dict()
            )

        manifest_path = self.manifest_dir / f"{run_id}.json"
        result = SilverBTransformResult(
            run_id=run_id,
            silver_a_manifest_path=str(silver_a_manifest_path),
            table_outputs=table_outputs,
            table_count=len(table_outputs),
            record_count=total_records,
            manifest_path=str(manifest_path),
        )
        manifest_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        return result

    def build_stock_positions(
        self,
        stock_lots: list[dict[str, Any]],
        item_lookup: dict[str, dict[str, Any]],
        location_lookup: dict[str, dict[str, Any]],
        erp_lookup: dict[tuple[str, str], dict[str, Any]],
        today: date,
    ) -> list[dict[str, Any]]:
        positions = []
        for lot in stock_lots:
            item = item_lookup.get(lot["item_id"], {})
            location = location_lookup.get(lot["location_id"], {})
            erp = erp_lookup.get((lot["item_id"], lot["location_id"]), {})
            quantity_on_hand = int(lot.get("quantity_on_hand") or 0)
            quantity_reserved = int(lot.get("quantity_reserved") or 0)
            quantity_available = max(0, quantity_on_hand - quantity_reserved)
            expiry_days = days_until(lot.get("expiry_date"), today)
            recall_status = lot.get("recall_status")
            sterility_status = lot.get("sterility_status")
            availability_status = self.availability_status(quantity_available, expiry_days, recall_status, sterility_status)

            positions.append(
                {
                    "stock_position_id": f"{lot['lot_id']}:{lot['location_id']}",
                    "lot_id": lot["lot_id"],
                    "item_id": lot["item_id"],
                    "canonical_name": lot.get("canonical_name") or item.get("canonical_name"),
                    "item_type": lot.get("item_type") or item.get("item_type"),
                    "clinical_category": item.get("clinical_category"),
                    "supplier_id": item.get("supplier_id") or erp.get("supplier_id"),
                    "location_id": lot["location_id"],
                    "location_name": lot.get("location_name") or location.get("location_name"),
                    "location_type": location.get("location_type"),
                    "quantity_on_hand": quantity_on_hand,
                    "quantity_reserved": quantity_reserved,
                    "quantity_available": quantity_available,
                    "erp_quantity_available": erp.get("quantity_available"),
                    "par_level": erp.get("par_level"),
                    "reorder_point": erp.get("reorder_point"),
                    "reorder_required": erp.get("reorder_required"),
                    "expiry_date": lot.get("expiry_date"),
                    "days_to_expiry": expiry_days,
                    "recall_status": recall_status,
                    "sterility_status": sterility_status,
                    "availability_status": availability_status,
                    "unit_cost_gbp": lot.get("unit_cost_gbp"),
                    "estimated_available_value_gbp": round(quantity_available * float(lot.get("unit_cost_gbp") or 0), 2),
                }
            )
        return positions

    def build_case_readiness(
        self,
        demand_rows: list[dict[str, Any]],
        stock_positions: list[dict[str, Any]],
        substitution_rules: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        available_by_item: dict[str, int] = defaultdict(int)
        statuses_by_item: dict[str, set[str]] = defaultdict(set)
        for position in stock_positions:
            available_by_item[position["item_id"]] += int(position.get("quantity_available") or 0)
            statuses_by_item[position["item_id"]].add(position.get("availability_status") or "unknown")

        substitutes_by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rule in substitution_rules:
            substitutes_by_item[rule["preferred_item_id"]].append(rule)

        readiness = []
        for demand in demand_rows:
            item_id = demand.get("item_id")
            required_quantity = int(demand.get("required_quantity") or 0)
            available_quantity = available_by_item.get(item_id, 0)
            shortage_quantity = max(0, required_quantity - available_quantity)
            substitute_options = [
                rule for rule in substitutes_by_item.get(item_id, [])
                if available_by_item.get(rule.get("substitute_item_id"), 0) > 0
            ]
            status = self.readiness_status(shortage_quantity, substitute_options)

            readiness.append(
                {
                    "case_demand_id": f"{demand['case_id']}:{item_id}:{demand.get('expected_item_name')}",
                    "case_id": demand["case_id"],
                    "scheduled_start": demand.get("scheduled_start"),
                    "required_by_time": demand.get("required_by_time"),
                    "procedure_name": demand.get("procedure_name"),
                    "surgeon_name": demand.get("surgeon_name"),
                    "item_id": item_id,
                    "expected_item_name": demand.get("expected_item_name"),
                    "item_type": demand.get("item_type"),
                    "clinical_criticality": demand.get("clinical_criticality"),
                    "required_quantity": required_quantity,
                    "available_quantity": available_quantity,
                    "shortage_quantity": shortage_quantity,
                    "stock_statuses": sorted(statuses_by_item.get(item_id, set())),
                    "substitute_item_ids": [rule["substitute_item_id"] for rule in substitute_options],
                    "readiness_status": status,
                }
            )
        return readiness

    def availability_status(
        self,
        quantity_available: int,
        days_to_expiry: int | None,
        recall_status: str | None,
        sterility_status: str | None,
    ) -> str:
        if quantity_available <= 0:
            return "unavailable"
        if recall_status == "quarantined":
            return "quarantined"
        if sterility_status == "awaiting_sterilisation":
            return "awaiting_sterilisation"
        if days_to_expiry is not None and days_to_expiry < 0:
            return "expired"
        if days_to_expiry is not None and days_to_expiry <= 30:
            return "expiring_soon"
        return "available"

    def readiness_status(self, shortage_quantity: int, substitute_options: list[dict[str, Any]]) -> str:
        if shortage_quantity <= 0:
            return "ready"
        if substitute_options:
            return "substitution_available"
        return "shortage"

    def write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as file:
            for row in rows:
                file.write(json.dumps(row) + "\n")


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Enrich Silver A stock inventory tables into Silver B facts.")
    parser.add_argument(
        "--silver-a-manifest",
        default=None,
        help="Silver A manifest path. Defaults to the latest manifest in data_lake/silver_a/manifests.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    manifest_path = Path(args.silver_a_manifest) if args.silver_a_manifest else latest_silver_a_manifest()
    result = SilverBTransformer().transform(manifest_path)
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()

