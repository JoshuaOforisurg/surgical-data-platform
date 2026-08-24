from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .models import EventType, LoanKitEvent


REQUIRED_COLUMNS = {
    "event_id",
    "kit_request_id",
    "case_id",
    "event_type",
    "occurred_at",
    "actor_role",
    "source_system",
}


def _optional(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


def _datetime(value: str | None, field: str, row_number: int) -> datetime | None:
    value = _optional(value)
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"row {row_number}: invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"row {row_number}: {field} must include a timezone")
    return parsed


def _boolean(value: str | None, field: str, row_number: int) -> bool | None:
    value = _optional(value)
    if value is None:
        return None
    if value.lower() in {"true", "1", "yes"}:
        return True
    if value.lower() in {"false", "0", "no"}:
        return False
    raise ValueError(f"row {row_number}: invalid {field}: {value}")


def read_events(path: Path) -> list[LoanKitEvent]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")

        events: list[LoanKitEvent] = []
        seen_event_ids: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            required_values = {name: _optional(row.get(name)) for name in REQUIRED_COLUMNS}
            empty = [name for name, value in required_values.items() if value is None]
            if empty:
                raise ValueError(f"row {row_number}: empty required fields: {', '.join(sorted(empty))}")
            event_id = required_values["event_id"] or ""
            if event_id in seen_event_ids:
                raise ValueError(f"row {row_number}: duplicate event_id: {event_id}")
            seen_event_ids.add(event_id)
            try:
                event_type = EventType(required_values["event_type"] or "")
            except ValueError as exc:
                raise ValueError(
                    f"row {row_number}: unknown event_type: {required_values['event_type']}"
                ) from exc

            check_result = _optional(row.get("check_result"))
            if check_result not in {None, "pass", "fail"}:
                raise ValueError(f"row {row_number}: invalid check_result: {check_result}")

            events.append(
                LoanKitEvent(
                    event_id=event_id,
                    kit_request_id=required_values["kit_request_id"] or "",
                    case_id=required_values["case_id"] or "",
                    event_type=event_type,
                    occurred_at=_datetime(row.get("occurred_at"), "occurred_at", row_number),  # type: ignore[arg-type]
                    actor_role=required_values["actor_role"] or "",
                    source_system=required_values["source_system"] or "",
                    required_by=_datetime(row.get("required_by"), "required_by", row_number),
                    supplier_id=_optional(row.get("supplier_id")),
                    check_result=check_result,
                    packaging_integrity_passed=_boolean(row.get("packaging_integrity_passed"), "packaging_integrity_passed", row_number),
                    sterility_indicator_passed=_boolean(row.get("sterility_indicator_passed"), "sterility_indicator_passed", row_number),
                    contents_verified=_boolean(row.get("contents_verified"), "contents_verified", row_number),
                    details=_optional(row.get("details")),
                )
            )
    return events
