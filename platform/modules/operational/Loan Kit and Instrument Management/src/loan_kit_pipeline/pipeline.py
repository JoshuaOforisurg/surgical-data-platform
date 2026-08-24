from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .io import read_events
from .rules import evaluate_lifecycle, group_events


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_pipeline(input_path: Path, output_dir: Path, minimum_lead_days: int = 14) -> dict:
    events = read_events(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    canonical_rows = []
    for event in sorted(events, key=lambda item: (item.kit_request_id, item.occurred_at, item.event_id)):
        row = asdict(event)
        row["event_type"] = event.event_type.value
        row["occurred_at"] = event.occurred_at.isoformat()
        row["required_by"] = event.required_by.isoformat() if event.required_by else ""
        canonical_rows.append(row)

    summaries = []
    exceptions = []
    for request_id, lifecycle in sorted(group_events(events).items()):
        summary, findings = evaluate_lifecycle(lifecycle, minimum_lead_days=minimum_lead_days)
        summaries.append(asdict(summary))
        exceptions.extend(asdict(item) for item in findings)

    canonical_path = output_dir / "canonical_events.csv"
    summary_path = output_dir / "kit_lifecycle_summary.csv"
    exceptions_path = output_dir / "exceptions.csv"
    _write_csv(canonical_path, canonical_rows, list(canonical_rows[0]) if canonical_rows else [])
    _write_csv(summary_path, summaries, list(summaries[0]) if summaries else [])
    exception_fields = ["kit_request_id", "case_id", "code", "severity", "message"]
    _write_csv(exceptions_path, exceptions, exception_fields)

    pipeline_summary = {
        "pipeline_version": __version__,
        "input_records": len(events),
        "kit_requests": len(summaries),
        "theatre_ready": sum(bool(item["theatre_ready"]) for item in summaries),
        "closed_workflows": sum(bool(item["workflow_closed"]) for item in summaries),
        "errors": sum(item["severity"] == "error" for item in exceptions),
        "warnings": sum(item["severity"] == "warning" for item in exceptions),
    }
    summary_json_path = output_dir / "pipeline_summary.json"
    summary_json_path.write_text(json.dumps(pipeline_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    output_files = [canonical_path, summary_path, exceptions_path, summary_json_path]
    manifest = {
        "pipeline_version": __version__,
        "input": {"path": input_path.name, "sha256": _sha256(input_path)},
        "outputs": [
            {"path": path.name, "sha256": _sha256(path)} for path in output_files
        ],
    }
    manifest_payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    manifest["batch_id"] = hashlib.sha256(manifest_payload.encode("utf-8")).hexdigest()[:16]
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return pipeline_summary
