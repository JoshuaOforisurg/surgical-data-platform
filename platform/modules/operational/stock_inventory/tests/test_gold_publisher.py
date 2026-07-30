from __future__ import annotations

import json
from pathlib import Path

from gold_cleaned.publisher import GoldInventoryPublisher


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row) + "\n")


def test_gold_publisher_creates_operational_outputs(tmp_path):
    run_id = "run_gold"
    silver_b_records = tmp_path / "silver_b" / "records" / run_id
    stock_positions = [
        {
            "item_id": "INV-001",
            "canonical_name": "Saw Blade",
            "supplier_id": "SUP-001",
            "location_id": "LOC-001",
            "location_name": "Main Store",
            "quantity_available": 1,
            "reorder_required": True,
            "par_level": 5,
            "reorder_point": 2,
            "availability_status": "available",
            "estimated_available_value_gbp": 10.0,
        },
        {
            "item_id": "INV-002",
            "canonical_name": "Critical Implant",
            "supplier_id": "SUP-002",
            "location_id": "LOC-001",
            "location_name": "Main Store",
            "quantity_available": 0,
            "reorder_required": False,
            "availability_status": "unavailable",
            "estimated_available_value_gbp": 0.0,
        },
    ]
    case_readiness = [
        {
            "case_id": "CASE-001",
            "scheduled_start": "2026-07-09T09:00:00+00:00",
            "procedure_name": "Test Procedure",
            "surgeon_name": "Mr Test",
            "preference_card_uid": "pref-test",
            "preference_card_version": 2,
            "item_id": "INV-001",
            "expected_item_name": "Saw Blade",
            "clinical_criticality": "required",
            "required_quantity": 3,
            "available_quantity": 1,
            "shortage_quantity": 2,
            "substitute_item_ids": ["INV-SUB"],
            "readiness_status": "substitution_available",
            "catalogue_match_status": "matched",
        },
        {
            "case_id": "CASE-001",
            "scheduled_start": "2026-07-09T09:00:00+00:00",
            "procedure_name": "Test Procedure",
            "surgeon_name": "Mr Test",
            "preference_card_uid": "pref-test",
            "preference_card_version": 2,
            "item_id": "INV-002",
            "expected_item_name": "Critical Implant",
            "clinical_criticality": "critical",
            "required_quantity": 1,
            "available_quantity": 0,
            "shortage_quantity": 1,
            "substitute_item_ids": [],
            "readiness_status": "shortage",
            "catalogue_match_status": "unmatched",
        },
    ]
    usage_analytics = [
        {
            "item_id": "INV-001",
            "canonical_name": "Saw Blade",
            "item_type": "disposable",
            "movement_count": 3,
            "issued_quantity": 2,
            "returned_quantity": 0,
            "wasted_quantity": 1,
            "case_issue_count": 1,
            "estimated_issue_value_gbp": 20.0,
        }
    ]
    stock_path = silver_b_records / "stock_positions.jsonl"
    readiness_path = silver_b_records / "case_readiness.jsonl"
    usage_path = silver_b_records / "usage_analytics.jsonl"
    _write_jsonl(stock_path, stock_positions)
    _write_jsonl(readiness_path, case_readiness)
    _write_jsonl(usage_path, usage_analytics)

    manifest_path = tmp_path / "silver_b" / "manifests" / f"{run_id}.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "table_outputs": [
                    {"dataset": "stock_positions", "output_path": str(stock_path), "records": 2},
                    {"dataset": "case_readiness", "output_path": str(readiness_path), "records": 2},
                    {"dataset": "usage_analytics", "output_path": str(usage_path), "records": 1},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = GoldInventoryPublisher(
        records_dir=tmp_path / "gold" / "records",
        manifest_dir=tmp_path / "gold" / "manifests",
    ).publish(manifest_path)

    assert result.artifact_count == 8
    gold_records = tmp_path / "gold" / "records" / run_id
    summary = json.loads((gold_records / "case_readiness_summary.json").read_text(encoding="utf-8"))
    shortages = json.loads((gold_records / "shortage_worklist.json").read_text(encoding="utf-8"))
    reorders = json.loads((gold_records / "reorder_worklist.json").read_text(encoding="utf-8"))
    usage = json.loads((gold_records / "usage_cost_summary.json").read_text(encoding="utf-8"))
    risk = json.loads((gold_records / "inventory_risk_summary.json").read_text(encoding="utf-8"))
    surgeon_readiness = json.loads(
        (gold_records / "surgeon_readiness_summary.json").read_text(encoding="utf-8")
    )
    procedure_readiness = json.loads(
        (gold_records / "procedure_readiness_summary.json").read_text(encoding="utf-8")
    )

    assert summary[0]["case_id"] == "CASE-001"
    assert summary[0]["overall_status"] == "critical_shortage"
    assert summary[0]["shortage_lines"] == 2
    assert summary[0]["unmapped_requirement_lines"] == 1
    assert len(shortages) == 2
    saw_blade_shortage = next(row for row in shortages if row["item_id"] == "INV-001")
    assert saw_blade_shortage["substitute_item_ids"] == "INV-SUB"
    assert reorders[0]["item_id"] == "INV-001"
    assert usage[0]["item_id"] == "INV-001"
    assert usage[0]["estimated_issue_value_gbp"] == 20.0
    assert risk["shortage_line_count"] == 2
    assert risk["reorder_position_count"] == 1
    assert risk["issued_quantity"] == 2
    assert risk["estimated_issue_value_gbp"] == 20.0
    assert surgeon_readiness[0]["surgeon_name"] == "Mr Test"
    assert surgeon_readiness[0]["critical_shortage_case_count"] == 1
    assert surgeon_readiness[0]["unmapped_requirement_count"] == 1
    assert procedure_readiness[0]["procedure_name"] == "Test Procedure"
    assert procedure_readiness[0]["surgeon_count"] == 1
    assert (gold_records / "case_readiness_summary.csv").exists()
