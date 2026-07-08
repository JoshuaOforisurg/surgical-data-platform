from __future__ import annotations

import json
from pathlib import Path

import pytest

from bronze_ingestion.loader.bronze_pipeline import BronzeInventoryPipeline


def _jsonl_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_bronze_pipeline_ingests_csv_json_and_jsonl(tmp_path):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    (source_dir / "item_catalogue.csv").write_text(
        "item_id,canonical_name,item_type\nINV-001,Saw Blade,disposable\n",
        encoding="utf-8",
    )
    (source_dir / "item_catalogue.json").write_text(
        json.dumps([{"item_id": "INV-001", "canonical_name": "Saw Blade", "item_type": "disposable"}]),
        encoding="utf-8",
    )
    (source_dir / "stock_locations.json").write_text(
        json.dumps([{"location_id": "LOC-001", "location_name": "Main Store"}]),
        encoding="utf-8",
    )
    (source_dir / "scanner_stock_events.jsonl").write_text(
        json.dumps({"event_id": "SCAN-001", "item_id": "INV-001"}) + "\n",
        encoding="utf-8",
    )

    pipeline = BronzeInventoryPipeline(
        raw_dir=tmp_path / "bronze" / "raw",
        records_dir=tmp_path / "bronze" / "records",
        manifest_dir=tmp_path / "bronze" / "manifests",
    )

    result = pipeline.ingest(source_dir, run_id="run_test")

    assert result.file_count == 4
    assert result.record_count == 4
    assert Path(result.manifest_path).exists()
    assert (tmp_path / "bronze" / "raw" / "run_test" / "item_catalogue.csv").exists()

    csv_records = _jsonl_rows(tmp_path / "bronze" / "records" / "run_test" / "item_catalogue__csv.jsonl")
    assert csv_records[0]["dataset"] == "item_catalogue"
    assert csv_records[0]["source_format"] == "csv"
    assert csv_records[0]["source_file_id"].startswith("run_test:item_catalogue.csv:")
    assert csv_records[0]["source_checksum_sha256"]
    assert csv_records[0]["canonical_for_silver"] is False
    assert csv_records[0]["raw_payload"]["canonical_name"] == "Saw Blade"

    json_records = _jsonl_rows(tmp_path / "bronze" / "records" / "run_test" / "item_catalogue__json.jsonl")
    assert json_records[0]["canonical_for_silver"] is True

    jsonl_records = _jsonl_rows(
        tmp_path / "bronze" / "records" / "run_test" / "scanner_stock_events__jsonl.jsonl"
    )
    assert jsonl_records[0]["record_id"] == "run_test:scanner_stock_events.jsonl:1"
    assert jsonl_records[0]["canonical_for_silver"] is True

    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    canonical_outputs = {
        output["source_file"]
        for output in manifest["record_outputs"]
        if output["canonical_for_silver"]
    }
    assert canonical_outputs == {
        "item_catalogue.json",
        "scanner_stock_events.jsonl",
        "stock_locations.json",
    }


def test_bronze_pipeline_rejects_missing_source(tmp_path):
    pipeline = BronzeInventoryPipeline(
        raw_dir=tmp_path / "raw",
        records_dir=tmp_path / "records",
        manifest_dir=tmp_path / "manifests",
    )

    with pytest.raises(FileNotFoundError):
        pipeline.ingest(tmp_path / "missing")


def test_bronze_pipeline_rejects_existing_run_id(tmp_path):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    (source_dir / "item_catalogue.csv").write_text(
        "item_id,canonical_name,item_type\nINV-001,Saw Blade,disposable\n",
        encoding="utf-8",
    )
    pipeline = BronzeInventoryPipeline(
        raw_dir=tmp_path / "raw",
        records_dir=tmp_path / "records",
        manifest_dir=tmp_path / "manifests",
    )

    pipeline.ingest(source_dir, run_id="run_test")

    with pytest.raises(FileExistsError):
        pipeline.ingest(source_dir, run_id="run_test")
