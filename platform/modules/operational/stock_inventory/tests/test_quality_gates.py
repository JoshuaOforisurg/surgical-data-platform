from __future__ import annotations

import json

from orchestration.quality_gates import PipelineQualityGateRunner
from orchestration.run_pipeline import StockInventoryOrchestrator


def _orchestrator(tmp_path):
    return StockInventoryOrchestrator(
        bronze_raw_dir=tmp_path / "bronze" / "raw",
        bronze_records_dir=tmp_path / "bronze" / "records",
        bronze_manifest_dir=tmp_path / "bronze" / "manifests",
        silver_a_records_dir=tmp_path / "silver_a" / "records",
        silver_a_manifest_dir=tmp_path / "silver_a" / "manifests",
        silver_b_records_dir=tmp_path / "silver_b" / "records",
        silver_b_manifest_dir=tmp_path / "silver_b" / "manifests",
        gold_records_dir=tmp_path / "gold" / "records",
        gold_manifest_dir=tmp_path / "gold" / "manifests",
        pipeline_manifest_dir=tmp_path / "pipeline_manifests",
    )


def test_quality_gates_pass_for_complete_pipeline_run(tmp_path):
    pipeline_result = _orchestrator(tmp_path).run(
        source_dir=tmp_path / "sources",
        run_id="run_quality_pass",
        event_count=5,
        movement_count=5,
        case_count=5,
        seed=42,
    )

    result = PipelineQualityGateRunner(output_dir=tmp_path / "quality" / "manifests").evaluate(
        pipeline_result.manifest_path
    )

    assert result.status == "passed"
    assert result.failure_count == 0
    assert result.check_count > 20
    checks = {check["name"]: check for check in result.checks}
    assert checks["gold.surgeon_readiness_summary.artifact_present"]["passed"] is True
    assert checks["gold.procedure_readiness_summary.artifact_present"]["passed"] is True
    assert (tmp_path / "quality" / "manifests" / "run_quality_pass.json").exists()


def test_quality_gates_fail_when_silver_a_invalid_records_exceed_threshold(tmp_path):
    pipeline_result = _orchestrator(tmp_path).run(
        source_dir=tmp_path / "sources",
        run_id="run_quality_fail",
        event_count=5,
        movement_count=5,
        case_count=5,
        seed=42,
    )
    silver_a_manifest_path = tmp_path / "silver_a" / "manifests" / "run_quality_fail.json"
    silver_a_manifest = json.loads(silver_a_manifest_path.read_text(encoding="utf-8"))
    silver_a_manifest["invalid_record_count"] = 2
    silver_a_manifest_path.write_text(json.dumps(silver_a_manifest), encoding="utf-8")

    result = PipelineQualityGateRunner(output_dir=tmp_path / "quality" / "manifests").evaluate(
        pipeline_result.manifest_path
    )

    invalid_record_check = next(
        check for check in result.checks if check["name"] == "silver_a.invalid_records_within_threshold"
    )

    assert result.status == "failed"
    assert result.failure_count == 1
    assert invalid_record_check["passed"] is False
    assert invalid_record_check["metadata"]["invalid_record_count"] == 2
