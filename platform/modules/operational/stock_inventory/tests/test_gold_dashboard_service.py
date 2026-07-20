from __future__ import annotations

import json
import os
from pathlib import Path

from streamlit_services.gold_dashboard_service import (
    dashboard_snapshot,
    dashboard_snapshot_from_object_store,
    latest_gold_manifest,
    list_gold_manifests,
    list_object_gold_manifests,
)


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
        "surgeon_readiness_summary": [
            {"surgeon_name": "Mr Test", "case_count": 2, "readiness_rate_pct": 50.0}
        ],
        "procedure_readiness_summary": [
            {"procedure_name": "Test Procedure", "case_count": 2, "readiness_rate_pct": 50.0}
        ],
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
    assert snapshot.surgeon_readiness[0]["surgeon_name"] == "Mr Test"
    assert snapshot.procedure_readiness[0]["procedure_name"] == "Test Procedure"


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


class FakeObjectStore:
    def __init__(self, objects: dict[str, object]):
        self.objects = {key: json.dumps(value) for key, value in objects.items()}

    def get_text(self, key: str) -> str:
        return self.objects[key]

    def list_objects(self, prefix: str) -> list[str]:
        return [key for key in self.objects if key.startswith(prefix)]


def test_dashboard_snapshot_loads_gold_artifacts_from_object_store():
    run_id = "run_object_store"
    root_prefix = "stock_inventory"
    manifest_key = f"{root_prefix}/runs/{run_id}/data_lake/gold/manifests/{run_id}.json"
    objects = {
        manifest_key: {
            "run_id": run_id,
            "artifacts": [
                {
                    "artifact": "case_readiness_summary",
                    "output_path": f"/app/data_lake/gold/records/{run_id}/case_readiness_summary.json",
                },
                {
                    "artifact": "shortage_worklist",
                    "output_path": f"/app/data_lake/gold/records/{run_id}/shortage_worklist.json",
                },
                {
                    "artifact": "reorder_worklist",
                    "output_path": f"/app/data_lake/gold/records/{run_id}/reorder_worklist.json",
                },
                {
                    "artifact": "usage_cost_summary",
                    "output_path": f"/app/data_lake/gold/records/{run_id}/usage_cost_summary.json",
                },
                {
                    "artifact": "inventory_risk_summary",
                    "output_path": f"/app/data_lake/gold/records/{run_id}/inventory_risk_summary.json",
                },
            ],
        },
        f"{root_prefix}/runs/{run_id}/data_lake/gold/records/{run_id}/case_readiness_summary.json": [
            {"case_id": "CASE-001", "overall_status": "ready"}
        ],
        f"{root_prefix}/runs/{run_id}/data_lake/gold/records/{run_id}/shortage_worklist.json": [],
        f"{root_prefix}/runs/{run_id}/data_lake/gold/records/{run_id}/reorder_worklist.json": [],
        f"{root_prefix}/runs/{run_id}/data_lake/gold/records/{run_id}/usage_cost_summary.json": [
            {"item_id": "INV-001"}
        ],
        f"{root_prefix}/runs/{run_id}/data_lake/gold/records/{run_id}/inventory_risk_summary.json": {
            "shortage_line_count": 0,
            "reorder_position_count": 0,
            "total_available_stock_value_gbp": 123.45,
            "estimated_issue_value_gbp": 10.0,
            "readiness_status_counts": {"ready": 1},
            "availability_status_counts": {"available": 2},
        },
    }
    object_store = FakeObjectStore(objects)

    options = list_object_gold_manifests(object_store, root_prefix)
    snapshot = dashboard_snapshot_from_object_store(object_store, manifest_key, root_prefix)

    assert options[0].run_id == run_id
    assert snapshot.run_id == run_id
    assert snapshot.case_count == 1
    assert snapshot.total_available_stock_value_gbp == 123.45
    assert snapshot.top_usage_costs[0]["item_id"] == "INV-001"
