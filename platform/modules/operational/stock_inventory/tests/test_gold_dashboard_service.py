from __future__ import annotations

import json
import os
from pathlib import Path

from streamlit_services.gold_dashboard_service import dashboard_snapshot, latest_gold_manifest, list_gold_manifests


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_dashboard_snapshot_loads_gold_operational_metrics(tmp_path):
    run_id = "run_dashboard"
    records_dir = tmp_path / "gold" / "records" / run_id
    artifacts = {
        "case_readiness_summary": [
            {"case_id": "CASE-001", "overall_status": "ready"},
            {"case_id": "CASE-002", "overall_status": "critical_shortage"},
        ],
        "shortage_worklist": [
            {"case_id": "CASE-002", "expected_item_name": "Critical Implant", "shortage_quantity": 1}
        ],
        "reorder_worklist": [
            {"item_id": "INV-001", "canonical_name": "Saw Blade", "quantity_available": 1}
        ],
        "usage_cost_summary": [
            {"item_id": "INV-001", "canonical_name": "Saw Blade", "estimated_issue_value_gbp": 20.0}
        ],
        "inventory_risk_summary": {
            "shortage_line_count": 1,
            "reorder_position_count": 1,
            "total_available_stock_value_gbp": 100.5,
            "estimated_issue_value_gbp": 20.0,
            "readiness_status_counts": {"ready": 3, "shortage": 1},
            "availability_status_counts": {"available": 10, "unavailable": 2},
        },
    }

    manifest_artifacts = []
    for artifact, payload in artifacts.items():
        output_path = records_dir / f"{artifact}.json"
        _write_json(output_path, payload)
        manifest_artifacts.append(
            {
                "artifact": artifact,
                "output_path": str(output_path),
                "records": len(payload) if isinstance(payload, list) else 1,
            }
        )

    manifest_path = tmp_path / "gold" / "manifests" / f"{run_id}.json"
    _write_json(
        manifest_path,
        {
            "run_id": run_id,
            "artifacts": manifest_artifacts,
        },
    )

    snapshot = dashboard_snapshot(manifest_path)

    assert snapshot.run_id == run_id
    assert snapshot.case_count == 2
    assert snapshot.ready_case_count == 1
    assert snapshot.critical_shortage_case_count == 1
    assert snapshot.shortage_line_count == 1
    assert snapshot.reorder_position_count == 1
    assert snapshot.total_available_stock_value_gbp == 100.5
    assert snapshot.estimated_issue_value_gbp == 20.0
    assert snapshot.top_shortages[0]["expected_item_name"] == "Critical Implant"
    assert snapshot.top_usage_costs[0]["item_id"] == "INV-001"


def test_gold_manifest_options_are_newest_first(tmp_path):
    first_manifest = tmp_path / "gold" / "manifests" / "run_first.json"
    second_manifest = tmp_path / "gold" / "manifests" / "run_second.json"
    _write_json(first_manifest, {"run_id": "run_first", "artifacts": []})
    _write_json(second_manifest, {"run_id": "run_second", "artifacts": []})

    os.utime(first_manifest, (1, 1))
    os.utime(second_manifest, (2, 2))

    options = list_gold_manifests(tmp_path / "gold" / "manifests")

    assert [option.run_id for option in options] == ["run_second", "run_first"]
    assert latest_gold_manifest(tmp_path / "gold" / "manifests") == second_manifest
