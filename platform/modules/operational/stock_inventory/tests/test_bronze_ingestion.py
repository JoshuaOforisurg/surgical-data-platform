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

    assert result.file_count == 3
    assert result.record_count == 3
    assert Path(result.manifest_path).exists()
    assert (tmp_path / "bronze" / "raw" / "run_test" / "item_catalogue.csv").exists()

    csv_records = _jsonl_rows(tmp_path / "bronze" / "records" / "run_test" / "item_catalogue__csv.jsonl")
    assert csv_records[0]["dataset"] == "item_catalogue"
    assert csv_records[0]["source_format"] == "csv"
    assert csv_records[0]["raw_payload"]["canonical_name"] == "Saw Blade"

    jsonl_records = _jsonl_rows(
        tmp_path / "bronze" / "records" / "run_test" / "scanner_stock_events__jsonl.jsonl"
    )
    assert jsonl_records[0]["record_id"] == "run_test:scanner_stock_events.jsonl:1"


def test_bronze_pipeline_rejects_missing_source(tmp_path):
    pipeline = BronzeInventoryPipeline(
        raw_dir=tmp_path / "raw",
        records_dir=tmp_path / "records",
        manifest_dir=tmp_path / "manifests",
    )

    with pytest.raises(FileNotFoundError):
        pipeline.ingest(tmp_path / "missing")

