from datetime import datetime, timezone
import unittest

from loan_kit_pipeline.models import EventType, LoanKitEvent
from loan_kit_pipeline.rules import evaluate_lifecycle


def event(event_type: EventType, hour: int, **kwargs) -> LoanKitEvent:
    return LoanKitEvent(
        event_id=f"E-{event_type.value}",
        kit_request_id="LKR-TEST",
        case_id="CASE-TEST",
        event_type=event_type,
        occurred_at=datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
        actor_role="tester",
        source_system="synthetic_test",
        **kwargs,
    )


def complete_pre_use_events() -> list[LoanKitEvent]:
    required_by = datetime(2026, 1, 20, tzinfo=timezone.utc)
    return [
        event(EventType.REQUEST_SUBMITTED, 1, required_by=required_by),
        event(EventType.REQUEST_APPROVED, 2),
        event(EventType.SUPPLIER_CONFIRMED, 3, supplier_id="SUP-1"),
        event(EventType.DELIVERY_RECEIVED, 4),
        event(EventType.RECEIPT_CHECK_COMPLETED, 5, check_result="pass"),
        event(EventType.SSD_HANDOVER, 6),
        event(EventType.SSD_RELEASED, 7, check_result="pass"),
        event(
            EventType.THEATRE_CHECK_COMPLETED,
            8,
            check_result="pass",
            packaging_integrity_passed=True,
            sterility_indicator_passed=True,
            contents_verified=True,
        ),
    ]


class LifecycleRuleTests(unittest.TestCase):
    def test_complete_explicit_checks_can_be_theatre_ready(self) -> None:
        summary, findings = evaluate_lifecycle(complete_pre_use_events())
        self.assertTrue(summary.theatre_ready)
        self.assertFalse([finding for finding in findings if finding.severity == "error"])

    def test_missing_explicit_check_cannot_be_theatre_ready(self) -> None:
        events = complete_pre_use_events()
        events[-1] = event(
            EventType.THEATRE_CHECK_COMPLETED,
            8,
            check_result="pass",
            packaging_integrity_passed=True,
            sterility_indicator_passed=None,
            contents_verified=True,
        )
        summary, findings = evaluate_lifecycle(events)
        self.assertFalse(summary.theatre_ready)
        self.assertIn("INCOMPLETE_THEATRE_CHECK", {finding.code for finding in findings})

    def test_failed_receipt_check_blocks_readiness(self) -> None:
        events = complete_pre_use_events()
        events[4] = event(EventType.RECEIPT_CHECK_COMPLETED, 5, check_result="fail")
        summary, findings = evaluate_lifecycle(events)
        self.assertFalse(summary.theatre_ready)
        self.assertIn("FAILED_CHECK", {finding.code for finding in findings})
