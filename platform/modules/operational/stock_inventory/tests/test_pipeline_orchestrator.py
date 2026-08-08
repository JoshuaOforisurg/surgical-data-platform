from __future__ import annotations

import json

from orchestration.run_pipeline import StockInventoryOrchestrator


class FakeMetadataRepository:
    def __init__(self):
        self.events = []

    def start_run(self, run_id, source_dir):
        self.events.append(("start", run_id, source_dir))

    def record_stage(self, run_id, stage, manifest_path, record_count):
        self.events.append(("stage", run_id, stage, manifest_path, record_count))

    def record_ingested_files(self, run_id, bronze_manifest_path):
        self.events.append(("ingested_files", run_id, bronze_manifest_path))

    def complete_run(self, run_id, pipeline_manifest_path):
        self.events.append(("complete", run_id, pipeline_manifest_path))

    def fail_run(self, run_id, error_message):
        self.events.append(("failed", run_id, error_message))


class FailingMetadataRepository(FakeMetadataRepository):
    def fail_run(self, run_id, error_message):
        raise RuntimeError("metadata database unavailable")


def test_orchestrator_runs_generator_to_gold(tmp_path):
    run_id = "run_orchestrator_test"
    source_dir = tmp_path / "sources"
    orchestrator = StockInventoryOrchestrator(
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

    result = orchestrator.run(
        source_dir=source_dir,
        run_id=run_id,
        event_count=5,
        movement_count=5,
        case_count=5,
        seed=42,
    )

    assert result.run_id == run_id
    assert result.generated_manifest_path == str(source_dir / "generation_manifest.json")
    assert [stage["stage"] for stage in result.stages] == ["bronze", "silver_a", "silver_b", "gold"]
    assert all(stage["record_count"] > 0 for stage in result.stages)

    pipeline_manifest = json.loads((tmp_path / "pipeline_manifests" / f"{run_id}.json").read_text(encoding="utf-8"))
    gold_manifest = json.loads((tmp_path / "gold" / "manifests" / f"{run_id}.json").read_text(encoding="utf-8"))

    assert pipeline_manifest["run_id"] == run_id
    assert pipeline_manifest["stages"][-1]["manifest_path"] == str(tmp_path / "gold" / "manifests" / f"{run_id}.json")
    assert gold_manifest["artifact_count"] == 8
    assert (tmp_path / "gold" / "records" / run_id / "case_readiness_summary.json").exists()


def test_orchestrator_can_clean_messy_csv_sources_to_gold(tmp_path):
    run_id = "run_messy_csv_orchestrator_test"
    source_dir = tmp_path / "sources"
    orchestrator = StockInventoryOrchestrator(
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

    result = orchestrator.run(
        source_dir=source_dir,
        run_id=run_id,
        event_count=5,
        movement_count=5,
        case_count=5,
        seed=42,
        canonical_format_priority=["csv", "jsonl", "json"],
    )

    generation_manifest = json.loads((source_dir / "generation_manifest.json").read_text(encoding="utf-8"))
    silver_a_manifest = json.loads((tmp_path / "silver_a" / "manifests" / f"{run_id}.json").read_text(encoding="utf-8"))

    assert generation_manifest["messy_sources"] is True
    assert generation_manifest["artifacts"]["stock_lots"]["csv_profile"] == "messy_hospital_spreadsheet"
    assert all(stage["record_count"] > 0 for stage in result.stages)
    assert silver_a_manifest["invalid_record_count"] == 0
    assert (tmp_path / "gold" / "records" / run_id / "inventory_risk_summary.json").exists()


def test_orchestrator_records_database_metadata_lifecycle(tmp_path):
    repository = FakeMetadataRepository()
    run_id = "run_metadata_test"
    orchestrator = StockInventoryOrchestrator(
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
        metadata_repository=repository,
    )

    orchestrator.run(
        source_dir=tmp_path / "sources",
        run_id=run_id,
        event_count=2,
        movement_count=2,
        case_count=2,
        seed=42,
    )

    assert repository.events[0][:2] == ("start", run_id)
    assert [event[2] for event in repository.events if event[0] == "stage"] == [
        "bronze",
        "silver_a",
        "silver_b",
        "gold",
    ]
    assert any(event[0] == "ingested_files" for event in repository.events)
    assert repository.events[-1][0] == "complete"


def test_orchestrator_preserves_pipeline_error_when_failure_recording_fails(tmp_path):
    orchestrator = StockInventoryOrchestrator(
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
        metadata_repository=FailingMetadataRepository(),
    )

    try:
        orchestrator.run(
            source_dir=tmp_path / "missing_sources",
            run_id="run_failure_recording_test",
            regenerate_sources=False,
        )
    except FileNotFoundError as exc:
        assert "missing_sources" in str(exc)
        assert any("metadata database unavailable" in note for note in exc.__notes__)
    else:
        raise AssertionError("Expected missing source failure")
