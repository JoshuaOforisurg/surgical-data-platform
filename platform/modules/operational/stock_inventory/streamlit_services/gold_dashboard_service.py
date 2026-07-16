from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from config.paths import GOLD_MANIFEST_DIR


@dataclass(frozen=True)
class GoldManifestOption:
    run_id: str
    manifest_path: str
    modified_at: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DashboardSnapshot:
    run_id: str
    case_count: int
    ready_case_count: int
    shortage_case_count: int
    critical_shortage_case_count: int
    shortage_line_count: int
    reorder_position_count: int
    total_available_stock_value_gbp: float
    estimated_issue_value_gbp: float
    readiness_status_counts: dict[str, int]
    availability_status_counts: dict[str, int]
    top_shortages: list[dict[str, Any]]
    top_reorders: list[dict[str, Any]]
    top_usage_costs: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def latest_gold_manifest(manifest_dir: Path = GOLD_MANIFEST_DIR) -> Path:
    manifests = [Path(option.manifest_path) for option in list_gold_manifests(manifest_dir)]
    if not manifests:
        raise FileNotFoundError(f"No Gold manifests found in {manifest_dir}")
    return manifests[0]


def list_gold_manifests(manifest_dir: Path = GOLD_MANIFEST_DIR) -> list[GoldManifestOption]:
    manifests = sorted(manifest_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    options: list[GoldManifestOption] = []
    for manifest_path in manifests:
        try:
            manifest = read_json(manifest_path)
            run_id = str(manifest.get("run_id") or manifest_path.stem)
        except (OSError, json.JSONDecodeError):
            run_id = manifest_path.stem
        options.append(
            GoldManifestOption(
                run_id=run_id,
                manifest_path=str(manifest_path),
                modified_at=manifest_path.stat().st_mtime,
            )
        )
    return options


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_paths(gold_manifest: dict[str, Any]) -> dict[str, Path]:
    paths = {}
    for artifact in gold_manifest.get("artifacts", []):
        output_path = Path(artifact["output_path"])
        if output_path.suffix == ".json":
            paths[artifact["artifact"]] = output_path
    return paths


def load_gold_artifacts(gold_manifest_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    gold_manifest = read_json(gold_manifest_path)
    paths = artifact_paths(gold_manifest)
    artifacts = {
        name: read_json(path)
        for name, path in paths.items()
    }
    return gold_manifest, artifacts


def dashboard_snapshot(gold_manifest_path: str | Path | None = None) -> DashboardSnapshot:
    manifest_path = Path(gold_manifest_path) if gold_manifest_path else latest_gold_manifest()
    gold_manifest, artifacts = load_gold_artifacts(manifest_path)

    case_summary = artifacts.get("case_readiness_summary", [])
    shortage_worklist = artifacts.get("shortage_worklist", [])
    reorder_worklist = artifacts.get("reorder_worklist", [])
    usage_cost_summary = artifacts.get("usage_cost_summary", [])
    risk_summary = artifacts.get("inventory_risk_summary", {})

    case_status_counts = Counter(row.get("overall_status") for row in case_summary)
    return DashboardSnapshot(
        run_id=str(gold_manifest["run_id"]),
        case_count=len(case_summary),
        ready_case_count=case_status_counts.get("ready", 0),
        shortage_case_count=case_status_counts.get("shortage", 0)
        + case_status_counts.get("substitution_available", 0),
        critical_shortage_case_count=case_status_counts.get("critical_shortage", 0),
        shortage_line_count=int(risk_summary.get("shortage_line_count") or 0),
        reorder_position_count=int(risk_summary.get("reorder_position_count") or 0),
        total_available_stock_value_gbp=float(risk_summary.get("total_available_stock_value_gbp") or 0),
        estimated_issue_value_gbp=float(risk_summary.get("estimated_issue_value_gbp") or 0),
        readiness_status_counts=risk_summary.get("readiness_status_counts") or {},
        availability_status_counts=risk_summary.get("availability_status_counts") or {},
        top_shortages=shortage_worklist[:10],
        top_reorders=reorder_worklist[:10],
        top_usage_costs=usage_cost_summary[:10],
    )
