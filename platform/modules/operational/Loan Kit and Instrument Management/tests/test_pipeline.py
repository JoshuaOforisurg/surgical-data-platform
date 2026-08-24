import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from loan_kit_pipeline.pipeline import run_pipeline

MODULE_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_EVENTS = MODULE_ROOT / "data/raw/synthetic/loan_kit_events.csv"


class PipelineTests(unittest.TestCase):
    def test_pipeline_produces_review_outputs(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            summary = run_pipeline(SYNTHETIC_EVENTS, output)
            self.assertEqual(summary["input_records"], 18)
            self.assertEqual(summary["kit_requests"], 2)
            self.assertEqual(summary["theatre_ready"], 1)
            self.assertEqual(summary["closed_workflows"], 1)

            expected = {
                "canonical_events.csv",
                "kit_lifecycle_summary.csv",
                "exceptions.csv",
                "pipeline_summary.json",
                "run_manifest.json",
            }
            self.assertEqual({path.name for path in output.iterdir()}, expected)

            with (output / "kit_lifecycle_summary.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["kit_request_id"], "LKR-001")
            self.assertEqual(rows[0]["theatre_ready"], "True")
            self.assertEqual(rows[1]["theatre_ready"], "False")

            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["batch_id"]), 16)
            self.assertEqual(len(manifest["outputs"]), 4)

    def test_pipeline_is_deterministic(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            run_pipeline(SYNTHETIC_EVENTS, first)
            run_pipeline(SYNTHETIC_EVENTS, second)
            self.assertEqual(
                (first / "run_manifest.json").read_bytes(),
                (second / "run_manifest.json").read_bytes(),
            )
