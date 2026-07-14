from __future__ import annotations

import json
from pathlib import Path

from generate_synthetic_data.main_synthetic_stock_generator import (
    GenerationConfig,
    generate_stock_sources,
    manifest_summary,
)


def test_generator_writes_source_files_and_manifest(tmp_path):
    manifest = generate_stock_sources(
        GenerationConfig(
            output_dir=tmp_path,
            event_count=5,
            movement_count=7,
            case_count=3,
            seed=42,
        )
    )

    expected_files = {
        "item_catalogue.csv",
        "item_catalogue.json",
        "stock_lots.csv",
        "stock_lots.json",
        "scanner_stock_events.csv",
        "scanner_stock_events.json",
        "scanner_stock_events.jsonl",
        "generation_manifest.json",
    }
    written_files = {path.name for path in tmp_path.iterdir() if path.is_file()}

    assert expected_files.issubset(written_files)
    assert manifest["artifacts"]["scanner_stock_events"]["records"] == 5
    assert manifest["artifacts"]["stock_movements"]["records"] == 7
    assert manifest["case_count"] == 3
    assert Path(manifest["artifacts"]["scanner_stock_events"]["jsonl"]).exists()


def test_manifest_summary_points_to_written_outputs(tmp_path):
    manifest = generate_stock_sources(GenerationConfig(output_dir=tmp_path, event_count=3, seed=42))

    summary = manifest_summary(manifest)

    assert "Synthetic stock inventory data generated." in summary
    assert f"Output directory: {tmp_path}" in summary
    assert f"Manifest: {tmp_path / 'generation_manifest.json'}" in summary


def test_generation_config_keeps_legacy_count_shortcut():
    config = GenerationConfig(count=30)

    assert config.event_count == 30
    assert config.movement_count == 30
    assert config.case_count == 10


def test_generator_is_reproducible_for_same_seed_and_run_date(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    config = {
        "event_count": 5,
        "movement_count": 5,
        "case_count": 5,
        "seed": 99,
    }

    first_manifest = generate_stock_sources(GenerationConfig(output_dir=first_dir, **config))
    second_manifest = generate_stock_sources(GenerationConfig(output_dir=second_dir, **config))

    first_catalogue = json.loads((first_dir / "item_catalogue.json").read_text(encoding="utf-8"))
    second_catalogue = json.loads((second_dir / "item_catalogue.json").read_text(encoding="utf-8"))
    first_events = json.loads((first_dir / "scanner_stock_events.json").read_text(encoding="utf-8"))
    second_events = json.loads((second_dir / "scanner_stock_events.json").read_text(encoding="utf-8"))

    assert first_manifest["generated_at"] == second_manifest["generated_at"]
    assert first_catalogue == second_catalogue
    assert first_events == second_events
