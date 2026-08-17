import json

from silver_transform.silver_a.silver_a_transformer import SilverTransformer
from silver_transform.silver_b.silver_b_batch_enricher import SilverBBatchEnricher


class StubEnrichmentEngine:
    def enrich(self, record):
        return {
            **record,
            "derived_metadata": {"confidence": 1.0},
            "quarantine_status": {"is_corrupted": False},
        }


def test_silver_a_writes_each_run_to_a_separate_directory(tmp_path):
    transformer = SilverTransformer(silver_a_dir=tmp_path / "silver_a")

    transformer.transform_records([{"surgeon_name": "First"}], run_id="run_first")
    transformer.transform_records([{"surgeon_name": "Second"}], run_id="run_second")

    first_path = tmp_path / "silver_a" / "runs" / "run_first" / "silver_a_cleaned.jsonl"
    second_path = tmp_path / "silver_a" / "runs" / "run_second" / "silver_a_cleaned.jsonl"

    assert json.loads(first_path.read_text(encoding="utf-8"))["surgeon_name"] == "First"
    assert json.loads(second_path.read_text(encoding="utf-8"))["surgeon_name"] == "Second"


def test_silver_b_writes_clean_and_quarantine_outputs_under_run_id(tmp_path):
    enricher = SilverBBatchEnricher(
        log_enabled=False,
        silver_a_dir=tmp_path / "silver_a",
        silver_b_dir=tmp_path / "silver_b",
    )
    enricher.engine = StubEnrichmentEngine()

    enricher.process([{"surgeon_name": "First"}], run_id="run_first")

    run_dir = tmp_path / "silver_b" / "runs" / "run_first"
    clean_path = run_dir / "silver_b_enriched.jsonl"
    quarantine_path = run_dir / "silver_b_quarantine.jsonl"

    assert json.loads(clean_path.read_text(encoding="utf-8"))["surgeon_name"] == "First"
    assert quarantine_path.read_text(encoding="utf-8") == ""
