from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

MODULE_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from config.paths import GOLD_MANIFEST_DIR, GOLD_RECORDS_DIR, SILVER_B_MANIFEST_DIR
from contracts.gold_contracts import GoldArtifactResult, GoldPublishResult


def latest_silver_b_manifest(manifest_dir: Path = SILVER_B_MANIFEST_DIR) -> Path:
    manifests = sorted(manifest_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not manifests:
        raise FileNotFoundError(f"No Silver B manifests found in {manifest_dir}")
    return manifests[0]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if isinstance(payload, list):
        return len(payload)
    return 1


def write_csv(path: Path, rows: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return 0
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


class GoldInventoryPublisher:
    def __init__(
        self,
        records_dir: Path = GOLD_RECORDS_DIR,
        manifest_dir: Path = GOLD_MANIFEST_DIR,
    ):
        self.records_dir = records_dir
        self.manifest_dir = manifest_dir

    def publish(self, silver_b_manifest_path: Path) -> GoldPublishResult:
        silver_b_manifest_path = Path(silver_b_manifest_path)
        silver_b_manifest = json.loads(silver_b_manifest_path.read_text(encoding="utf-8"))
        run_id = str(silver_b_manifest["run_id"])
        tables = self.load_silver_b_tables(silver_b_manifest)

        stock_positions = tables.get("stock_positions", [])
        case_readiness = tables.get("case_readiness", [])
        artifacts = {
            "case_readiness_summary": self.case_readiness_summary(case_readiness),
            "shortage_worklist": self.shortage_worklist(case_readiness),
            "reorder_worklist": self.reorder_worklist(stock_positions),
            "inventory_risk_summary": self.inventory_risk_summary(stock_positions, case_readiness),
        }

        run_records_dir = self.records_dir / run_id
        artifact_results: list[dict[str, Any]] = []
        total_records = 0

        for artifact, payload in artifacts.items():
            json_path = run_records_dir / f"{artifact}.json"
            records = write_json(json_path, payload)
            total_records += records
            artifact_results.append(
                GoldArtifactResult(
                    artifact=artifact,
                    output_path=str(json_path),
                    records=records,
                ).to_dict()
            )

        summary_csv_path = run_records_dir / "case_readiness_summary.csv"
        summary_csv_records = write_csv(summary_csv_path, artifacts["case_readiness_summary"])
        artifact_results.append(
            GoldArtifactResult(
                artifact="case_readiness_summary_csv",
                output_path=str(summary_csv_path),
                records=summary_csv_records,
            ).to_dict()
        )
        total_records += summary_csv_records

        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.manifest_dir / f"{run_id}.json"
        result = GoldPublishResult(
            run_id=run_id,
            silver_b_manifest_path=str(silver_b_manifest_path),
            artifacts=artifact_results,
            artifact_count=len(artifact_results),
            record_count=total_records,
            manifest_path=str(manifest_path),
        )
        manifest_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        return result

    def load_silver_b_tables(self, silver_b_manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        tables = {}
        for output in silver_b_manifest.get("table_outputs", []):
            tables[output["dataset"]] = read_jsonl(Path(output["output_path"]))
        return tables

    def case_readiness_summary(self, case_readiness: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in case_readiness:
            grouped[row["case_id"]].append(row)

        summaries = []
        for case_id, rows in sorted(grouped.items()):
            status_counts = Counter(row["readiness_status"] for row in rows)
            shortage_lines = sum(1 for row in rows if row["shortage_quantity"] > 0)
            critical_shortage_lines = sum(
                1 for row in rows
                if row["shortage_quantity"] > 0 and row.get("clinical_criticality") == "critical"
            )
            overall_status = self.overall_case_status(status_counts, critical_shortage_lines)
            first = rows[0]
            summaries.append(
                {
                    "case_id": case_id,
                    "scheduled_start": first.get("scheduled_start"),
                    "procedure_name": first.get("procedure_name"),
                    "surgeon_name": first.get("surgeon_name"),
                    "required_lines": len(rows),
                    "ready_lines": status_counts.get("ready", 0),
                    "shortage_lines": shortage_lines,
                    "substitution_available_lines": status_counts.get("substitution_available", 0),
                    "critical_shortage_lines": critical_shortage_lines,
                    "overall_status": overall_status,
                }
            )
        return summaries

    def shortage_worklist(self, case_readiness: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = [
            {
                "case_id": row["case_id"],
                "scheduled_start": row.get("scheduled_start"),
                "procedure_name": row.get("procedure_name"),
                "item_id": row.get("item_id"),
                "expected_item_name": row.get("expected_item_name"),
                "clinical_criticality": row.get("clinical_criticality"),
                "required_quantity": row.get("required_quantity"),
                "available_quantity": row.get("available_quantity"),
                "shortage_quantity": row.get("shortage_quantity"),
                "substitute_item_ids": ";".join(row.get("substitute_item_ids") or []),
                "readiness_status": row.get("readiness_status"),
            }
            for row in case_readiness
            if int(row.get("shortage_quantity") or 0) > 0
        ]
        return sorted(rows, key=lambda row: (row.get("scheduled_start") or "", row["case_id"], row["expected_item_name"] or ""))

    def reorder_worklist(self, stock_positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for row in stock_positions:
            if not row.get("reorder_required"):
                continue
            key = (row["item_id"], row["location_id"])
            current = grouped.setdefault(
                key,
                {
                    "item_id": row["item_id"],
                    "canonical_name": row.get("canonical_name"),
                    "supplier_id": row.get("supplier_id"),
                    "location_id": row.get("location_id"),
                    "location_name": row.get("location_name"),
                    "quantity_available": 0,
                    "par_level": row.get("par_level"),
                    "reorder_point": row.get("reorder_point"),
                    "estimated_available_value_gbp": 0.0,
                },
            )
            current["quantity_available"] += int(row.get("quantity_available") or 0)
            current["estimated_available_value_gbp"] = round(
                float(current["estimated_available_value_gbp"]) + float(row.get("estimated_available_value_gbp") or 0),
                2,
            )

        return sorted(grouped.values(), key=lambda row: (row.get("supplier_id") or "", row["canonical_name"] or ""))

    def inventory_risk_summary(
        self,
        stock_positions: list[dict[str, Any]],
        case_readiness: list[dict[str, Any]],
    ) -> dict[str, Any]:
        availability_counts = Counter(row.get("availability_status") for row in stock_positions)
        readiness_counts = Counter(row.get("readiness_status") for row in case_readiness)
        stock_value = round(
            sum(float(row.get("estimated_available_value_gbp") or 0) for row in stock_positions),
            2,
        )
        return {
            "stock_position_count": len(stock_positions),
            "case_demand_line_count": len(case_readiness),
            "total_available_stock_value_gbp": stock_value,
            "availability_status_counts": dict(sorted(availability_counts.items())),
            "readiness_status_counts": dict(sorted(readiness_counts.items())),
            "shortage_line_count": sum(1 for row in case_readiness if int(row.get("shortage_quantity") or 0) > 0),
            "reorder_position_count": sum(1 for row in stock_positions if row.get("reorder_required")),
        }

    def overall_case_status(self, status_counts: Counter, critical_shortage_lines: int) -> str:
        if critical_shortage_lines:
            return "critical_shortage"
        if status_counts.get("shortage", 0):
            return "shortage"
        if status_counts.get("substitution_available", 0):
            return "substitution_available"
        return "ready"


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Publish Gold stock inventory operational outputs.")
    parser.add_argument(
        "--silver-b-manifest",
        default=None,
        help="Silver B manifest path. Defaults to the latest manifest in data_lake/silver_b/manifests.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    manifest_path = Path(args.silver_b_manifest) if args.silver_b_manifest else latest_silver_b_manifest()
    result = GoldInventoryPublisher().publish(manifest_path)
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()

