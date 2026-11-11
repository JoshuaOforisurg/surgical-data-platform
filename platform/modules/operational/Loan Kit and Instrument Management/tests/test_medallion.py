from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from loan_kit_pipeline.medallion import LoanKitMedallionPipeline


MODULE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = MODULE_ROOT / "data/raw/synthetic_v2"
AS_OF = datetime.fromisoformat("2026-09-21T12:00:00+01:00")


class MedallionPipelineTests(unittest.TestCase):
    def run_pipeline(self, output: Path) -> dict:
        return LoanKitMedallionPipeline().run(SOURCE_DIR, output, AS_OF)

    def test_all_four_stages_and_gold_outputs_are_created(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            manifest = self.run_pipeline(output)
            self.assertEqual(manifest["pipeline_version"], "0.2.0")
            self.assertEqual(set(manifest["stages"]), {"landing", "bronze", "silver", "gold"})
            self.assertEqual(manifest["stages"]["landing"]["file_count"], 5)
            self.assertEqual(manifest["stages"]["silver"]["requests"], 4)
            for artifact in (
                "upcoming_worklist", "at_risk_cases", "receipt_discrepancies",
                "ssd_status", "theatre_readiness", "outstanding_returns",
                "supplier_performance",
            ):
                self.assertTrue((output / "gold" / f"{artifact}.csv").is_file())
            self.assertTrue((output / "gold/quality_report.json").is_file())

    def test_operational_views_expose_risk_and_ownership(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            self.run_pipeline(output)
            with (output / "gold/at_risk_cases.csv").open(newline="", encoding="utf-8") as handle:
                risk_rows = {row["kit_request_id"]: row for row in csv.DictReader(handle)}
            self.assertIn("LKR-102", risk_rows)
            self.assertIn("open_errors", risk_rows["LKR-102"]["risk_reasons"])
            self.assertEqual(risk_rows["LKR-102"]["next_owner"], "sterile_services")
            self.assertIn("LKR-104", risk_rows)
            self.assertIn("approval_not_complete", risk_rows["LKR-104"]["risk_reasons"])

    def test_item_and_tray_discrepancies_block_readiness(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            self.run_pipeline(output)
            with (output / "gold/theatre_readiness.csv").open(newline="", encoding="utf-8") as handle:
                readiness = {row["kit_request_id"]: row for row in csv.DictReader(handle)}
            self.assertEqual(readiness["LKR-101"]["theatre_ready"], "True")
            self.assertEqual(readiness["LKR-102"]["theatre_ready"], "False")
            self.assertGreater(int(readiness["LKR-102"]["item_errors"]), 0)
            with (output / "gold/receipt_discrepancies.csv").open(newline="", encoding="utf-8") as handle:
                discrepancies = list(csv.DictReader(handle))
            self.assertEqual(discrepancies[0]["kit_id"], "KIT-102")

    def test_quality_report_keeps_deliberate_failures_visible(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            manifest = self.run_pipeline(output)
            quality = json.loads((output / "gold/quality_report.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["quality_status"], "failed")
            self.assertEqual(quality["status"], "failed")
            codes = {row["code"] for row in quality["findings"]}
            self.assertIn("TRAY_COUNT_MISMATCH", codes)
            self.assertIn("ITEM_SHORTAGE", codes)
            self.assertIn("MISSING_STAGE", codes)

    def test_run_is_deterministic(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.run_pipeline(root / "first")
            second = self.run_pipeline(root / "second")
            self.assertEqual(first["run_id"], second["run_id"])
            self.assertEqual(
                (root / "first/gold/theatre_readiness.csv").read_bytes(),
                (root / "second/gold/theatre_readiness.csv").read_bytes(),
            )


class MedallionValidationTests(unittest.TestCase):
    def test_missing_source_is_rejected(self) -> None:
        with TemporaryDirectory() as source_directory, TemporaryDirectory() as output_directory:
            with self.assertRaisesRegex(ValueError, "missing source files"):
                LoanKitMedallionPipeline().run(Path(source_directory), Path(output_directory), AS_OF)

    def test_as_of_requires_timezone(self) -> None:
        with TemporaryDirectory() as output_directory:
            with self.assertRaisesRegex(ValueError, "timezone"):
                LoanKitMedallionPipeline().run(
                    SOURCE_DIR,
                    Path(output_directory),
                    datetime.fromisoformat("2026-09-21T12:00:00"),
                )

    def test_documented_cli_runs_end_to_end(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "loan_kit_pipeline.operational_cli",
                    "--source-dir",
                    str(SOURCE_DIR),
                    "--output",
                    str(output),
                    "--as-of",
                    AS_OF.isoformat(),
                ],
                cwd=MODULE_ROOT,
                env={**os.environ, "PYTHONPATH": str(MODULE_ROOT / "src")},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"status": "completed"', result.stdout)
            self.assertTrue((output / "gold/theatre_readiness.csv").is_file())
