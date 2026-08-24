from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from loan_kit_pipeline.io import read_events

MODULE_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_EVENTS = MODULE_ROOT / "data/raw/synthetic/loan_kit_events.csv"


class ReadEventsTests(unittest.TestCase):
    def test_synthetic_source_loads(self) -> None:
        events = read_events(SYNTHETIC_EVENTS)
        self.assertEqual(len(events), 18)
        self.assertEqual({event.kit_request_id for event in events}, {"LKR-001", "LKR-002"})

    def test_duplicate_event_id_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "events.csv"
            source.write_text(
                "event_id,kit_request_id,case_id,event_type,occurred_at,actor_role,source_system\n"
                "E1,L1,C1,request_submitted,2026-01-01T10:00:00+00:00,surgeon,form\n"
                "E1,L1,C1,request_approved,2026-01-01T11:00:00+00:00,lead,form\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate event_id"):
                read_events(source)

    def test_timezone_is_required(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "events.csv"
            source.write_text(
                "event_id,kit_request_id,case_id,event_type,occurred_at,actor_role,source_system\n"
                "E1,L1,C1,request_submitted,2026-01-01T10:00:00,surgeon,form\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "must include a timezone"):
                read_events(source)
