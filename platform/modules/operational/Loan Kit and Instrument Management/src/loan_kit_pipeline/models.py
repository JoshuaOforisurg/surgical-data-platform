from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    REQUEST_SUBMITTED = "request_submitted"
    REQUEST_APPROVED = "request_approved"
    SUPPLIER_CONFIRMED = "supplier_confirmed"
    DELIVERY_RECEIVED = "delivery_received"
    RECEIPT_CHECK_COMPLETED = "receipt_check_completed"
    SSD_HANDOVER = "ssd_handover"
    SSD_RELEASED = "ssd_released"
    THEATRE_CHECK_COMPLETED = "theatre_check_completed"
    KIT_USED = "kit_used"
    USAGE_RECONCILED = "usage_reconciled"
    RETURN_PREPARED = "return_prepared"
    SUPPLIER_COLLECTED = "supplier_collected"
    WORKFLOW_CLOSED = "workflow_closed"


EVENT_ORDER = {event: position for position, event in enumerate(EventType, start=1)}


@dataclass(frozen=True)
class LoanKitEvent:
    event_id: str
    kit_request_id: str
    case_id: str
    event_type: EventType
    occurred_at: datetime
    actor_role: str
    source_system: str
    required_by: datetime | None = None
    supplier_id: str | None = None
    check_result: str | None = None
    packaging_integrity_passed: bool | None = None
    sterility_indicator_passed: bool | None = None
    contents_verified: bool | None = None
    details: str | None = None


@dataclass(frozen=True)
class PipelineException:
    kit_request_id: str
    case_id: str
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class LifecycleSummary:
    kit_request_id: str
    case_id: str
    current_status: str
    supplier_id: str
    requested_at: str
    required_by: str
    request_lead_days: str
    last_event_at: str
    theatre_ready: bool
    workflow_closed: bool
    event_count: int
    error_count: int
    warning_count: int
