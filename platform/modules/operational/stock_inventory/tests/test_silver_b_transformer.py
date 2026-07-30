from __future__ import annotations

import json
from pathlib import Path

from silver_transform.silver_b.transformer import SilverBTransformer


def _write_silver_a_table(path: Path, dataset: str, payloads: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for idx, payload in enumerate(payloads, start=1):
            file.write(
                json.dumps(
                    {
                        "silver_record_id": f"silver_a:run_b:{dataset}:{idx}",
                        "run_id": "run_b",
                        "dataset": dataset,
                        "source_record_id": f"run_b:{dataset}.json:{idx}",
                        "source_file_id": f"run_b:{dataset}.json:abc",
                        "source_checksum_sha256": "abc",
                        "source_row_number": idx,
                        "transformed_at": "2026-07-08T00:00:00+00:00",
                        "validation_errors": [],
                        "payload": payload,
                    }
                )
                + "\n"
            )


def _jsonl_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_silver_b_builds_stock_positions_and_case_readiness(tmp_path):
    records_dir = tmp_path / "silver_a" / "records" / "run_b"
    tables = {
        "item_catalogue": [
            {
                "item_id": "INV-001",
                "canonical_name": "Saw Blade",
                "item_type": "disposable",
                "clinical_category": "Power tool consumables",
                "supplier_id": "SUP-001",
            },
            {
                "item_id": "INV-SUB",
                "canonical_name": "Alt Saw Blade",
                "item_type": "disposable",
                "clinical_category": "Power tool consumables",
                "supplier_id": "SUP-001",
            },
        ],
        "stock_locations": [
            {
                "location_id": "LOC-001",
                "location_name": "Main Store",
                "location_type": "stockroom",
            }
        ],
        "stock_lots": [
            {
                "lot_id": "LOT-001",
                "item_id": "INV-001",
                "canonical_name": "Saw Blade",
                "item_type": "disposable",
                "location_id": "LOC-001",
                "location_name": "Main Store",
                "quantity_on_hand": 2,
                "quantity_reserved": 1,
                "expiry_date": "2099-01-01",
                "recall_status": "clear",
                "sterility_status": "sterile",
                "unit_cost_gbp": 10.0,
            },
            {
                "lot_id": "LOT-SUB",
                "item_id": "INV-SUB",
                "canonical_name": "Alt Saw Blade",
                "item_type": "disposable",
                "location_id": "LOC-001",
                "location_name": "Main Store",
                "quantity_on_hand": 5,
                "quantity_reserved": 0,
                "expiry_date": "2099-01-01",
                "recall_status": "clear",
                "sterility_status": "sterile",
                "unit_cost_gbp": 8.0,
            },
        ],
        "erp_stock_balances": [
            {
                "item_id": "INV-001",
                "location_id": "LOC-001",
                "quantity_available": 1,
                "par_level": 5,
                "reorder_point": 2,
                "reorder_required": True,
                "supplier_id": "SUP-001",
            }
        ],
        "upcoming_case_demand": [
            {
                "case_id": "CASE-001",
                "scheduled_start": "2026-07-09T09:00:00+00:00",
                "required_by_time": "2026-07-09T07:00:00+00:00",
                "procedure_name": "Test Procedure",
                "surgeon_name": "Mr Test",
                "preference_card_uid": "pref-test",
                "preference_card_version": 2,
                "preference_source": "surgeon_preference_gold",
                "item_id": "INV-001",
                "expected_item_name": "Saw Blade",
                "item_type": "disposable",
                "clinical_criticality": "required",
                "required_quantity": 3,
                "catalogue_match_status": "matched",
            }
        ],
        "substitution_rules": [
            {
                "preferred_item_id": "INV-001",
                "substitute_item_id": "INV-SUB",
            }
        ],
        "stock_movements": [
            {
                "movement_id": "MOVE-001",
                "item_id": "INV-001",
                "canonical_name": "Saw Blade",
                "movement_type": "issue",
                "quantity": 2,
                "case_id": "CASE-001",
            },
            {
                "movement_id": "MOVE-002",
                "item_id": "INV-001",
                "canonical_name": "Saw Blade",
                "movement_type": "waste",
                "quantity": 1,
                "case_id": "",
            },
        ],
    }
    table_outputs = []
    for dataset, payloads in tables.items():
        output_path = records_dir / f"{dataset}.jsonl"
        _write_silver_a_table(output_path, dataset, payloads)
        table_outputs.append(
            {
                "dataset": dataset,
                "output_path": str(output_path),
                "records": len(payloads),
                "invalid_records": 0,
            }
        )

    manifest_path = tmp_path / "silver_a" / "manifests" / "run_b.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": "run_b",
                "table_outputs": table_outputs,
            }
        ),
        encoding="utf-8",
    )

    result = SilverBTransformer(
        records_dir=tmp_path / "silver_b" / "records",
        manifest_dir=tmp_path / "silver_b" / "manifests",
    ).transform(manifest_path)

    assert result.table_count == 3
    positions = _jsonl_rows(tmp_path / "silver_b" / "records" / "run_b" / "stock_positions.jsonl")
    readiness = _jsonl_rows(tmp_path / "silver_b" / "records" / "run_b" / "case_readiness.jsonl")
    usage = _jsonl_rows(tmp_path / "silver_b" / "records" / "run_b" / "usage_analytics.jsonl")

    primary_position = next(row for row in positions if row["item_id"] == "INV-001")
    assert primary_position["quantity_available"] == 1
    assert primary_position["availability_status"] == "available"
    assert primary_position["reorder_required"] is True
    assert primary_position["estimated_available_value_gbp"] == 10.0

    assert readiness[0]["required_quantity"] == 3
    assert readiness[0]["available_quantity"] == 1
    assert readiness[0]["allocated_quantity"] == 1
    assert readiness[0]["remaining_quantity_after_allocation"] == 0
    assert readiness[0]["shortage_quantity"] == 2
    assert readiness[0]["substitute_item_ids"] == ["INV-SUB"]
    assert readiness[0]["readiness_status"] == "substitution_available"
    assert readiness[0]["preference_card_uid"] == "pref-test"
    assert readiness[0]["preference_card_version"] == 2
    assert readiness[0]["preference_source"] == "surgeon_preference_gold"
    assert readiness[0]["catalogue_match_status"] == "matched"

    assert usage[0]["item_id"] == "INV-001"
    assert usage[0]["movement_count"] == 2
    assert usage[0]["issued_quantity"] == 2
    assert usage[0]["wasted_quantity"] == 1
    assert usage[0]["case_issue_count"] == 1
    assert usage[0]["estimated_issue_value_gbp"] == 20.0


def test_case_readiness_excludes_unsafe_stock_and_allocates_in_schedule_order():
    transformer = SilverBTransformer()
    stock_positions = [
        {
            "item_id": "INV-001",
            "quantity_available": 3,
            "availability_status": "available",
        },
        {
            "item_id": "INV-001",
            "quantity_available": 100,
            "availability_status": "quarantined",
        },
    ]
    demand_rows = [
        {
            "case_id": "CASE-LATER",
            "scheduled_start": "2026-07-10T09:00:00+00:00",
            "item_id": "INV-001",
            "expected_item_name": "Saw Blade",
            "required_quantity": 2,
        },
        {
            "case_id": "CASE-EARLIER",
            "scheduled_start": "2026-07-09T09:00:00+00:00",
            "item_id": "INV-001",
            "expected_item_name": "Saw Blade",
            "required_quantity": 2,
        },
    ]

    readiness = transformer.build_case_readiness(demand_rows, stock_positions, [])

    assert [row["case_id"] for row in readiness] == ["CASE-EARLIER", "CASE-LATER"]
    assert readiness[0]["available_quantity"] == 3
    assert readiness[0]["allocated_quantity"] == 2
    assert readiness[0]["readiness_status"] == "ready"
    assert readiness[1]["available_quantity"] == 1
    assert readiness[1]["allocated_quantity"] == 1
    assert readiness[1]["shortage_quantity"] == 1
    assert readiness[1]["readiness_status"] == "shortage"
    assert readiness[1]["stock_statuses"] == ["available", "quarantined"]
