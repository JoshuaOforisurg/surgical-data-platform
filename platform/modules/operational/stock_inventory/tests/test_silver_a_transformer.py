from __future__ import annotations

import json
from pathlib import Path

from bronze_ingestion.loader.bronze_pipeline import BronzeInventoryPipeline
from silver_transform.silver_a.transformer import SilverATransformer


def _jsonl_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_silver_a_transforms_only_canonical_bronze_outputs(tmp_path):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    (source_dir / "item_catalogue.csv").write_text(
        "item_id,canonical_name,item_type,sterile_required,source_profile_count\n"
        "INV-CSV,Saw Blade,disposable,false,1\n",
        encoding="utf-8",
    )
    (source_dir / "item_catalogue.json").write_text(
        json.dumps(
            [
                {
                    "item_id": "INV-JSON",
                    "canonical_name": "Saw Blade",
                    "item_type": "disposable",
                    "sterile_required": True,
                    "source_profile_count": 2,
                    "active_status": "active",
                }
            ]
        ),
        encoding="utf-8",
    )
    (source_dir / "scanner_stock_events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "SCAN-001",
                "item_id": "INV-JSON",
                "event_type": "stock_count",
                "event_timestamp": "2026-07-08T06:00:00+00:00",
                "quantity_delta": "2",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    bronze = BronzeInventoryPipeline(
        raw_dir=tmp_path / "bronze" / "raw",
        records_dir=tmp_path / "bronze" / "records",
        manifest_dir=tmp_path / "bronze" / "manifests",
    ).ingest(source_dir, run_id="run_silver")

    result = SilverATransformer(
        records_dir=tmp_path / "silver_a" / "records",
        manifest_dir=tmp_path / "silver_a" / "manifests",
    ).transform(Path(bronze.manifest_path))

    assert result.table_count == 2
    assert result.record_count == 2
    assert result.invalid_record_count == 0
    assert Path(result.manifest_path).exists()

    item_rows = _jsonl_rows(tmp_path / "silver_a" / "records" / "run_silver" / "item_catalogue.jsonl")
    item_payload = item_rows[0]["payload"]
    assert item_payload["item_id"] == "INV-JSON"
    assert item_payload["sterile_required"] is True
    assert item_payload["source_profile_count"] == 2
    assert item_payload["active_status"] == "active"
    assert item_rows[0]["source_file_id"].startswith("run_silver:item_catalogue.json:")
    assert item_rows[0]["source_checksum_sha256"]

    event_rows = _jsonl_rows(tmp_path / "silver_a" / "records" / "run_silver" / "scanner_stock_events.jsonl")
    event_payload = event_rows[0]["payload"]
    assert event_payload["quantity_delta"] == 2
    assert event_payload["event_timestamp"] == "2026-07-08T06:00:00+00:00"


def test_silver_a_records_validation_errors_without_dropping_rows(tmp_path):
    bronze_records_dir = tmp_path / "bronze" / "records" / "run_bad"
    bronze_records_dir.mkdir(parents=True)
    record_path = bronze_records_dir / "item_catalogue__json.jsonl"
    record_path.write_text(
        json.dumps(
            {
                "record_id": "run_bad:item_catalogue.json:1",
                "run_id": "run_bad",
                "source_file_id": "run_bad:item_catalogue.json:abc123",
                "source_checksum_sha256": "abc123",
                "dataset": "item_catalogue",
                "source_file": "item_catalogue.json",
                "source_format": "json",
                "canonical_for_silver": True,
                "source_row_number": 1,
                "ingested_at": "2026-07-08T06:00:00+00:00",
                "raw_payload": {"canonical_name": "Saw Blade", "item_type": "disposable"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "bronze" / "manifests" / "run_bad.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": "run_bad",
                "record_outputs": [
                    {
                        "dataset": "item_catalogue",
                        "source_file": "item_catalogue.json",
                        "source_file_id": "run_bad:item_catalogue.json:abc123",
                        "record_path": str(record_path),
                        "records": 1,
                        "canonical_for_silver": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = SilverATransformer(
        records_dir=tmp_path / "silver_a" / "records",
        manifest_dir=tmp_path / "silver_a" / "manifests",
    ).transform(manifest_path)

    assert result.record_count == 1
    assert result.invalid_record_count == 1
    rows = _jsonl_rows(tmp_path / "silver_a" / "records" / "run_bad" / "item_catalogue.jsonl")
    assert "item_id: required" in rows[0]["validation_errors"]


def test_silver_a_cleans_messy_spreadsheet_values(tmp_path):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    (source_dir / "stock_lots.csv").write_text(
        "Lot Id,Item Id,Location Id,Qty On Hand,Qty Reserved,Unit Cost GBP,Expiry Date,Last Counted At\n"
        "LOT-001,INV-001,LOC-001,\" 1,234 \", 5 ,\"GBP 1,234.50\",08/07/2026,08/07/2026 13:45\n",
        encoding="utf-8",
    )

    bronze = BronzeInventoryPipeline(
        raw_dir=tmp_path / "bronze" / "raw",
        records_dir=tmp_path / "bronze" / "records",
        manifest_dir=tmp_path / "bronze" / "manifests",
    ).ingest(source_dir, run_id="run_messy")

    result = SilverATransformer(
        records_dir=tmp_path / "silver_a" / "records",
        manifest_dir=tmp_path / "silver_a" / "manifests",
    ).transform(Path(bronze.manifest_path))

    assert result.invalid_record_count == 0
    rows = _jsonl_rows(tmp_path / "silver_a" / "records" / "run_messy" / "stock_lots.jsonl")
    payload = rows[0]["payload"]
    assert payload["quantity_on_hand"] == 1234
    assert payload["quantity_reserved"] == 5
    assert payload["unit_cost_gbp"] == 1234.5
    assert payload["expiry_date"] == "2026-07-08"
    assert payload["last_counted_at"] == "2026-07-08T13:45:00"
