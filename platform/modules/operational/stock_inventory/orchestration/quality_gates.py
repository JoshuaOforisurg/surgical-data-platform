from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

MODULE_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from config.paths import PIPELINE_MANIFEST_DIR, QUALITY_MANIFEST_DIR
from contracts.pipeline_contracts import PipelineQualityCheck, PipelineQualityResult
from metadata.repository import metadata_repository_from_settings


REQUIRED_STAGES = ("bronze", "silver_a", "silver_b", "gold")
REQUIRED_SILVER_B_TABLES = ("stock_positions", "case_readiness", "usage_analytics")
REQUIRED_GOLD_ARTIFACTS = (
    "case_readiness_summary",
    "shortage_worklist",
    "reorder_worklist",
    "usage_cost_summary",
    "inventory_risk_summary",
    "surgeon_readiness_summary",
    "procedure_readiness_summary",
    "case_readiness_summary_csv",
)


def latest_pipeline_manifest(manifest_dir: Path = PIPELINE_MANIFEST_DIR) -> Path:
    manifests = sorted(manifest_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not manifests:
        raise FileNotFoundError(f"No pipeline manifests found in {manifest_dir}")
    return manifests[0]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class PipelineQualityGateRunner:
    def __init__(self, output_dir: Path = QUALITY_MANIFEST_DIR, metadata_repository: Any | None = None):
        self.output_dir = output_dir
        self.metadata_repository = metadata_repository

    def evaluate(
        self,
        pipeline_manifest_path: Path,
        max_invalid_silver_a_records: int = 0,
    ) -> PipelineQualityResult:
        pipeline_manifest_path = Path(pipeline_manifest_path)
        pipeline_manifest = read_json(pipeline_manifest_path)
        run_id = str(pipeline_manifest["run_id"])
        checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        checks: list[PipelineQualityCheck] = []
        stages = {stage.get("stage"): stage for stage in pipeline_manifest.get("stages", [])}
        checks.extend(self.required_stage_checks(stages))
        checks.extend(self.stage_manifest_checks(stages))

        silver_a_manifest = self.stage_manifest(stages, "silver_a")
        if silver_a_manifest is not None:
            checks.extend(self.silver_a_checks(silver_a_manifest, max_invalid_silver_a_records))

        silver_b_manifest = self.stage_manifest(stages, "silver_b")
        if silver_b_manifest is not None:
            checks.extend(self.silver_b_checks(silver_b_manifest))

        gold_manifest = self.stage_manifest(stages, "gold")
        if gold_manifest is not None:
            checks.extend(self.gold_checks(gold_manifest))

        failure_count = sum(1 for check in checks if not check.passed)
        status = "passed" if failure_count == 0 else "failed"

        self.output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.output_dir / f"{run_id}.json"
        result = PipelineQualityResult(
            run_id=run_id,
            status=status,
            checked_at=checked_at,
            pipeline_manifest_path=str(pipeline_manifest_path),
            checks=[check.to_dict() for check in checks],
            check_count=len(checks),
            failure_count=failure_count,
            manifest_path=str(manifest_path),
        )
        manifest_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        if self.metadata_repository is not None:
            self.metadata_repository.record_quality_result(result)
        return result

    def required_stage_checks(self, stages: dict[str, dict[str, Any]]) -> list[PipelineQualityCheck]:
        return [
            self.check(
                name=f"{stage}.stage_present",
                passed=stage in stages,
                message=f"{stage} stage is present in the pipeline manifest",
                metadata={"stage": stage},
            )
            for stage in REQUIRED_STAGES
        ]

    def stage_manifest_checks(self, stages: dict[str, dict[str, Any]]) -> list[PipelineQualityCheck]:
        checks = []
        for stage, payload in stages.items():
            manifest_path_value = str(payload.get("manifest_path") or "")
            manifest_path = Path(manifest_path_value)
            record_count = int(payload.get("record_count") or 0)
            checks.append(
                self.check(
                    name=f"{stage}.manifest_exists",
                    passed=bool(manifest_path_value) and manifest_path.exists(),
                    message=f"{stage} manifest exists",
                    metadata={"manifest_path": str(manifest_path)},
                )
            )
            checks.append(
                self.check(
                    name=f"{stage}.record_count_positive",
                    passed=record_count > 0,
                    message=f"{stage} record count is greater than zero",
                    metadata={"record_count": record_count},
                )
            )
        return checks

    def stage_manifest(self, stages: dict[str, dict[str, Any]], stage: str) -> dict[str, Any] | None:
        manifest_path = Path(str(stages.get(stage, {}).get("manifest_path") or ""))
        if not manifest_path.exists():
            return None
        return read_json(manifest_path)

    def silver_a_checks(
        self,
        silver_a_manifest: dict[str, Any],
        max_invalid_silver_a_records: int,
    ) -> list[PipelineQualityCheck]:
        invalid_records = int(silver_a_manifest.get("invalid_record_count") or 0)
        checks = [
            self.check(
                name="silver_a.invalid_records_within_threshold",
                passed=invalid_records <= max_invalid_silver_a_records,
                message="Silver A invalid records are within threshold",
                metadata={
                    "invalid_record_count": invalid_records,
                    "max_invalid_silver_a_records": max_invalid_silver_a_records,
                },
            )
        ]
        checks.extend(self.output_file_checks("silver_a", silver_a_manifest.get("table_outputs", []), "dataset"))
        return checks

    def silver_b_checks(self, silver_b_manifest: dict[str, Any]) -> list[PipelineQualityCheck]:
        outputs = silver_b_manifest.get("table_outputs", [])
        datasets = {output.get("dataset") for output in outputs}
        checks = [
            self.check(
                name=f"silver_b.{dataset}.table_present",
                passed=dataset in datasets,
                message=f"Silver B {dataset} table is present",
                metadata={"dataset": dataset},
            )
            for dataset in REQUIRED_SILVER_B_TABLES
        ]
        checks.extend(self.output_file_checks("silver_b", outputs, "dataset"))
        return checks

    def gold_checks(self, gold_manifest: dict[str, Any]) -> list[PipelineQualityCheck]:
        artifacts = gold_manifest.get("artifacts", [])
        artifact_names = {artifact.get("artifact") for artifact in artifacts}
        checks = [
            self.check(
                name=f"gold.{artifact}.artifact_present",
                passed=artifact in artifact_names,
                message=f"Gold {artifact} artifact is present",
                metadata={"artifact": artifact},
            )
            for artifact in REQUIRED_GOLD_ARTIFACTS
        ]
        checks.extend(self.output_file_checks("gold", artifacts, "artifact"))
        return checks

    def output_file_checks(
        self,
        stage: str,
        outputs: list[dict[str, Any]],
        label_field: str,
    ) -> list[PipelineQualityCheck]:
        checks = []
        for output in outputs:
            label = str(output.get(label_field))
            output_path = Path(str(output.get("output_path") or ""))
            checks.append(
                self.check(
                    name=f"{stage}.{label}.output_exists",
                    passed=output_path.exists(),
                    message=f"{stage} output file exists for {label}",
                    metadata={"output_path": str(output_path)},
                )
            )
        return checks

    def check(
        self,
        name: str,
        passed: bool,
        message: str,
        metadata: dict[str, Any],
        severity: str = "error",
    ) -> PipelineQualityCheck:
        return PipelineQualityCheck(
            name=name,
            passed=passed,
            severity=severity,
            message=message,
            metadata=metadata,
        )


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate quality gates for a stock inventory pipeline run.")
    parser.add_argument(
        "--pipeline-manifest",
        default=None,
        help="Pipeline manifest path. Defaults to the latest data_lake/pipeline_manifests entry.",
    )
    parser.add_argument(
        "--max-invalid-silver-a-records",
        type=int,
        default=0,
        help="Maximum Silver A invalid records allowed before the gate fails.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    manifest_path = Path(args.pipeline_manifest) if args.pipeline_manifest else latest_pipeline_manifest()
    from config.settings import load_settings

    repository = metadata_repository_from_settings(load_settings())
    result = PipelineQualityGateRunner(metadata_repository=repository).evaluate(
        manifest_path,
        max_invalid_silver_a_records=args.max_invalid_silver_a_records,
    )
    print(json.dumps(result.to_dict(), indent=2))
    if result.status != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
