import pytest

from orchestration.quality_gate import PipelineQualityError, evaluate_silver_quality


def test_quality_gate_allows_clinical_quarantine_when_counts_reconcile():
    summary = evaluate_silver_quality(
        {
            "total_records": 20,
            "successful": 19,
            "quarantined": 1,
            "failed": 0,
            "avg_confidence": 0.968,
        },
        output_record_count=20,
    )

    assert summary["passed"] is True
    assert summary["quarantined"] == 1


def test_quality_gate_blocks_technical_processing_failures():
    with pytest.raises(PipelineQualityError, match="technical processing failure"):
        evaluate_silver_quality(
            {
                "total_records": 20,
                "successful": 18,
                "quarantined": 1,
                "failed": 1,
            },
            output_record_count=20,
        )


@pytest.mark.parametrize(
    ("stats", "output_count", "message"),
    [
        (
            {"total_records": 0, "successful": 0, "quarantined": 0, "failed": 0},
            0,
            "empty input batch",
        ),
        (
            {"total_records": 3, "successful": 1, "quarantined": 1, "failed": 0},
            3,
            "metrics do not reconcile",
        ),
        (
            {"total_records": 3, "successful": 2, "quarantined": 1, "failed": 0},
            2,
            "output count does not reconcile",
        ),
    ],
)
def test_quality_gate_blocks_incomplete_or_inconsistent_batches(stats, output_count, message):
    with pytest.raises(PipelineQualityError, match=message):
        evaluate_silver_quality(stats, output_record_count=output_count)
