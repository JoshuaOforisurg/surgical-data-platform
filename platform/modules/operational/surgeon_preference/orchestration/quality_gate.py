from __future__ import annotations

from typing import Any, Mapping


class PipelineQualityError(RuntimeError):
    """Raised when technical processing failures make a run unsafe to publish."""


def evaluate_silver_quality(
    stats: Mapping[str, Any],
    output_record_count: int,
) -> dict[str, Any]:
    """Reconcile Silver-B metrics and block technical failures before Gold."""
    summary = {
        "total_records": int(stats.get("total_records") or 0),
        "successful": int(stats.get("successful") or 0),
        "quarantined": int(stats.get("quarantined") or 0),
        "failed": int(stats.get("failed") or 0),
        "output_records": int(output_record_count),
        "avg_confidence": float(stats.get("avg_confidence") or 0.0),
    }

    if summary["total_records"] == 0:
        raise PipelineQualityError("Silver quality gate rejected an empty input batch.")

    classified = summary["successful"] + summary["quarantined"] + summary["failed"]
    if classified != summary["total_records"]:
        raise PipelineQualityError(
            "Silver quality metrics do not reconcile: "
            f"classified={classified}, total={summary['total_records']}."
        )

    if summary["output_records"] != summary["total_records"]:
        raise PipelineQualityError(
            "Silver output count does not reconcile with input: "
            f"output={summary['output_records']}, total={summary['total_records']}."
        )

    if summary["failed"]:
        raise PipelineQualityError(
            f"Silver quality gate detected {summary['failed']} technical processing failure(s)."
        )

    summary["passed"] = True
    return summary
