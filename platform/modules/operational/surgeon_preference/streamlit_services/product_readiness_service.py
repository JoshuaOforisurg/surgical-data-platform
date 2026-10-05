from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Iterable

import pandas as pd


READY = "ready"
NEEDS_ATTENTION = "needs_attention"
BLOCKED = "blocked"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class ReadinessSignal:
    area: str
    status: str
    summary: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _normalise_status(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _count_by_status(rows: Iterable[dict[str, Any]], field: str = "status") -> Counter:
    return Counter(_normalise_status(row.get(field)) for row in rows)


def gold_dataset_signal(current_gold: pd.DataFrame | None) -> ReadinessSignal:
    if current_gold is None or current_gold.empty:
        return ReadinessSignal(
            area="Gold dataset",
            status=BLOCKED,
            summary="No current preference cards",
            detail="Run the pipeline before frontline teams use the app.",
        )

    missing_sections = []
    required_sections = [
        "instrument_set",
        "equipment",
        "consumables",
        "disposables",
        "special_instructions",
    ]
    for section in required_sections:
        if section not in current_gold.columns:
            missing_sections.append(section)
            continue
        empty_count = current_gold[section].fillna("").astype(str).str.strip().isin({"", "N/A"}).sum()
        if empty_count:
            missing_sections.append(f"{section} ({int(empty_count)} blank)")

    if missing_sections:
        return ReadinessSignal(
            area="Gold dataset",
            status=NEEDS_ATTENTION,
            summary=f"{len(current_gold)} current cards with incomplete sections",
            detail="Check: " + ", ".join(missing_sections),
        )

    return ReadinessSignal(
        area="Gold dataset",
        status=READY,
        summary=f"{len(current_gold)} current cards available",
        detail="Core frontline sections are populated.",
    )


def draft_workflow_signal(drafts: list[dict[str, Any]]) -> ReadinessSignal:
    if not drafts:
        return ReadinessSignal(
            area="Draft workflow",
            status=READY,
            summary="No draft backlog",
            detail="There are no submitted edits waiting for review or publish.",
        )

    counts = _count_by_status(drafts)
    pending_review = counts.get("pending_review", 0)
    approved_pending_publish = counts.get("approved_pending_publish", 0)
    changes_requested = counts.get("changes_requested", 0)

    if pending_review or approved_pending_publish:
        return ReadinessSignal(
            area="Draft workflow",
            status=NEEDS_ATTENTION,
            summary=(
                f"{pending_review} waiting for review, "
                f"{approved_pending_publish} waiting for publish"
            ),
            detail=f"{changes_requested} drafts have changes requested.",
        )

    return ReadinessSignal(
        area="Draft workflow",
        status=READY,
        summary=f"{len(drafts)} draft records archived",
        detail="No active review or publish queue.",
    )


def pipeline_metadata_signal(metadata: dict[str, Any]) -> ReadinessSignal:
    health = metadata.get("health") or {}
    if health and not health.get("reachable"):
        return ReadinessSignal(
            area="Pipeline metadata",
            status=NEEDS_ATTENTION,
            summary="Postgres metadata is not reachable",
            detail=str(health.get("error") or "Object storage may still work, but audit visibility is reduced."),
        )

    runs = metadata.get("runs")
    if not isinstance(runs, pd.DataFrame) or runs.empty:
        return ReadinessSignal(
            area="Pipeline metadata",
            status=UNKNOWN,
            summary="No pipeline run metadata loaded",
            detail="Run history is not available in the metadata catalogue.",
        )

    latest = runs.iloc[0].to_dict()
    latest_status = _normalise_status(latest.get("status"))
    if latest_status != "completed":
        return ReadinessSignal(
            area="Pipeline metadata",
            status=BLOCKED,
            summary=f"Latest run is {latest_status or 'unknown'}",
            detail=str(latest.get("error_message") or latest.get("run_id") or "Check pipeline logs."),
        )

    return ReadinessSignal(
        area="Pipeline metadata",
        status=READY,
        summary=f"Latest run completed: {latest.get('run_id')}",
        detail=f"Records processed: {latest.get('records_processed', 'N/A')}",
    )


def contract_signal(manifest: dict[str, Any] | None) -> ReadinessSignal:
    if not manifest:
        return ReadinessSignal(
            area="Pipeline contract",
            status=UNKNOWN,
            summary="No run manifest loaded",
            detail="Contract validation status is only available on newer pipeline runs.",
        )

    contract = manifest.get("contract_summary") or {}
    quality = manifest.get("quality_summary") or {}
    if contract.get("passed") and quality.get("passed"):
        return ReadinessSignal(
            area="Pipeline contract",
            status=READY,
            summary=f"{contract.get('records_validated', 'N/A')} Silver records validated",
            detail=f"Contract: {contract.get('contract_version', 'N/A')}; quality gate passed.",
        )

    missing = []
    if not contract.get("passed"):
        missing.append("contract validation")
    if not quality.get("passed"):
        missing.append("quality gate")
    return ReadinessSignal(
        area="Pipeline contract",
        status=NEEDS_ATTENTION,
        summary="Latest manifest is missing validation evidence",
        detail="Missing: " + ", ".join(missing),
    )


def build_product_readiness_summary(
    current_gold: pd.DataFrame | None,
    drafts: list[dict[str, Any]],
    metadata: dict[str, Any],
    latest_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    signals = [
        gold_dataset_signal(current_gold),
        draft_workflow_signal(drafts),
        pipeline_metadata_signal(metadata),
        contract_signal(latest_manifest),
    ]
    status_order = {BLOCKED: 3, NEEDS_ATTENTION: 2, UNKNOWN: 1, READY: 0}
    overall = max(signals, key=lambda signal: status_order[signal.status]).status
    return {
        "overall_status": overall,
        "signals": [signal.to_dict() for signal in signals],
    }
