from __future__ import annotations

from collections import defaultdict

from .models import EVENT_ORDER, EventType, LifecycleSummary, LoanKitEvent, PipelineException


MANDATORY_PRE_USE_EVENTS = (
    EventType.REQUEST_SUBMITTED,
    EventType.REQUEST_APPROVED,
    EventType.SUPPLIER_CONFIRMED,
    EventType.DELIVERY_RECEIVED,
    EventType.RECEIPT_CHECK_COMPLETED,
    EventType.SSD_HANDOVER,
    EventType.SSD_RELEASED,
    EventType.THEATRE_CHECK_COMPLETED,
)


def group_events(events: list[LoanKitEvent]) -> dict[str, list[LoanKitEvent]]:
    grouped: dict[str, list[LoanKitEvent]] = defaultdict(list)
    for event in events:
        grouped[event.kit_request_id].append(event)
    return {key: sorted(value, key=lambda item: (item.occurred_at, item.event_id)) for key, value in grouped.items()}


def evaluate_lifecycle(events: list[LoanKitEvent], minimum_lead_days: int = 14) -> tuple[LifecycleSummary, list[PipelineException]]:
    if not events:
        raise ValueError("cannot evaluate an empty lifecycle")
    events = sorted(events, key=lambda item: (item.occurred_at, item.event_id))
    first = events[0]
    exceptions: list[PipelineException] = []

    case_ids = {event.case_id for event in events}
    if len(case_ids) != 1:
        exceptions.append(PipelineException(first.kit_request_id, first.case_id, "MULTIPLE_CASE_IDS", "error", "One kit request is associated with multiple case identifiers."))

    present_types = {event.event_type for event in events}
    for required in MANDATORY_PRE_USE_EVENTS:
        if required not in present_types:
            exceptions.append(PipelineException(first.kit_request_id, first.case_id, "MISSING_STAGE", "error", f"Missing required pre-use event: {required.value}."))

    highest_order = 0
    for event in events:
        current_order = EVENT_ORDER[event.event_type]
        if current_order < highest_order:
            exceptions.append(PipelineException(first.kit_request_id, first.case_id, "EVENT_SEQUENCE", "warning", f"{event.event_type.value} was recorded after a later workflow stage."))
        highest_order = max(highest_order, current_order)

    for event in events:
        if event.check_result == "fail":
            exceptions.append(PipelineException(first.kit_request_id, first.case_id, "FAILED_CHECK", "error", f"Failed check recorded at {event.event_type.value}."))

    request = next((event for event in events if event.event_type == EventType.REQUEST_SUBMITTED), None)
    required_by = next((event.required_by for event in events if event.required_by is not None), None)
    lead_days: int | None = None
    if request and required_by:
        lead_days = (required_by - request.occurred_at).days
        if lead_days < minimum_lead_days:
            exceptions.append(PipelineException(first.kit_request_id, first.case_id, "SHORT_LEAD_TIME", "warning", f"Request lead time was {lead_days} days; configured minimum is {minimum_lead_days}."))
    elif request:
        exceptions.append(PipelineException(first.kit_request_id, first.case_id, "MISSING_REQUIRED_BY", "error", "No required-by timestamp was recorded."))

    theatre_checks = [event for event in events if event.event_type == EventType.THEATRE_CHECK_COMPLETED]
    explicit_theatre_check = any(
        event.check_result == "pass"
        and event.packaging_integrity_passed is True
        and event.sterility_indicator_passed is True
        and event.contents_verified is True
        for event in theatre_checks
    )
    has_ssd_release = EventType.SSD_RELEASED in present_types
    has_errors = any(item.severity == "error" for item in exceptions)
    theatre_ready = has_ssd_release and explicit_theatre_check and not has_errors

    if theatre_checks and not explicit_theatre_check:
        exceptions.append(PipelineException(first.kit_request_id, first.case_id, "INCOMPLETE_THEATRE_CHECK", "error", "Theatre readiness checks were not all explicitly passed."))
        theatre_ready = False

    errors = sum(item.severity == "error" for item in exceptions)
    warnings = sum(item.severity == "warning" for item in exceptions)
    supplier_id = next((event.supplier_id for event in reversed(events) if event.supplier_id), "")
    summary = LifecycleSummary(
        kit_request_id=first.kit_request_id,
        case_id=first.case_id,
        current_status=events[-1].event_type.value,
        supplier_id=supplier_id,
        requested_at=request.occurred_at.isoformat() if request else "",
        required_by=required_by.isoformat() if required_by else "",
        request_lead_days=str(lead_days) if lead_days is not None else "",
        last_event_at=events[-1].occurred_at.isoformat(),
        theatre_ready=theatre_ready,
        workflow_closed=EventType.WORKFLOW_CLOSED in present_types,
        event_count=len(events),
        error_count=errors,
        warning_count=warnings,
    )
    return summary, exceptions
