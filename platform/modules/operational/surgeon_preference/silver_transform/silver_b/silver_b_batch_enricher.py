from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json

from silver_transform.silver_b.clinical_enrichment import ClinicalEnrichmentEngine
from config.paths import SILVER_B_DIR, SILVER_A_DIR


class SilverBBatchEnricher:
    def __init__(
        self,
        log_enabled: bool = True,
        silver_a_dir: Path = SILVER_A_DIR,
        silver_b_dir: Path = SILVER_B_DIR,
    ):
        self.engine = ClinicalEnrichmentEngine()
        self.log_enabled = log_enabled
        self.silver_a_dir = Path(silver_a_dir)
        self.silver_b_dir = Path(silver_b_dir)

        # Runtime metrics updated to track quarantine counts
        self.stats = {
            "total_records": 0,
            "successful": 0,
            "quarantined": 0,
            "failed": 0,
            "avg_confidence": 0.0,
            "start_time": None,
            "end_time": None,
        }

    def _log(self, message: str):
        if self.log_enabled:
            print(f"[Silver-B Batch] {message}")

    def _save_silver_a_input(
        self,
        records: List[Dict[str, Any]],
        run_id: str | None = None,
    ) -> None:
        try:
            output_dir = (
                self.silver_a_dir / "runs" / run_id if run_id else self.silver_a_dir
            )
            silver_a_file = output_dir / "silver_a_input.jsonl"
            silver_a_file.parent.mkdir(parents=True, exist_ok=True)
            with open(silver_a_file, "w", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record) + "\n")
            self._log(f"Saved Silver-A input data to {silver_a_file}")
        except Exception as e:
            self._log(f"Failed to save Silver-A input data: {str(e)}")

    def _process_single(self, record: Dict[str, Any]) -> Dict[str, Any]:
        try:
            enriched = self.engine.enrich(record)
            confidence = enriched.get("derived_metadata", {}).get("confidence", 0.0)

            # Check the status injected by our new ClinicalEnrichmentEngine
            is_corrupted = enriched.get("quarantine_status", {}).get("is_corrupted", False)

            enriched["_enrichment_meta"] = {
                "processed_at": datetime.now().isoformat(),
                "status": "QUARANTINED" if is_corrupted else "SUCCESS",
                "confidence": confidence,
            }

            if is_corrupted:
                self.stats["quarantined"] += 1
            else:
                self.stats["successful"] += 1

            return enriched

        except Exception as e:
            self.stats["failed"] += 1
            return {
                **record,
                "_enrichment_meta": {
                    "processed_at": datetime.now().isoformat(),
                    "status": "FAILED",
                    "error": str(e),
                    "confidence": 0.0,
                },
                "quarantine_status": {"is_corrupted": True, "quarantine_reason": "PIPELINE_EXCEPTION"},
                "clinical_resolution": None,
                "clinical_validation": {
                    "valid": False,
                    "flags": ["ENRICHMENT_EXCEPTION"],
                    "missing_expected_items": [],
                },
            }

    def process(
        self,
        records: List[Dict[str, Any]],
        run_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        self.stats.update({
            "total_records": len(records),
            "successful": 0,
            "quarantined": 0,
            "failed": 0,
            "avg_confidence": 0.0,
            "start_time": datetime.now().isoformat(),
        })

        self._log(f"Starting batch enrichment for {len(records)} records")
        self._save_silver_a_input(records, run_id=run_id)

        enriched_records = []
        confidence_sum = 0.0
        confidence_count = 0

        for idx, record in enumerate(records):
            enriched = self._process_single(record)
            enriched_records.append(enriched)

            confidence = enriched["_enrichment_meta"].get("confidence", 0.0)
            confidence_sum += confidence
            confidence_count += 1

            if (idx + 1) % 50 == 0:
                self._log(f"Processed {idx + 1}/{len(records)} records")

        self.stats["avg_confidence"] = (
            confidence_sum / confidence_count if confidence_count else 0.0
        )
        self.stats["end_time"] = datetime.now().isoformat()

        self._log(
            f"Completed batch | "
            f"Success (Clean): {self.stats['successful']} | "
            f"Quarantined: {self.stats['quarantined']} | "
            f"Failed: {self.stats['failed']} | "
            f"Avg Confidence: {self.stats['avg_confidence']:.3f}"
        )

        # Route and save the final files based on corruption status
        self._save_split_records(enriched_records, run_id=run_id)

        return enriched_records

    def _save_split_records(
        self,
        records: List[Dict[str, Any]],
        run_id: str | None = None,
    ) -> None:
        """Splits output into production-ready data and a separate quarantine stream."""
        try:
            output_dir = (
                self.silver_b_dir / "runs" / run_id if run_id else self.silver_b_dir
            )
            output_dir.mkdir(parents=True, exist_ok=True)

            clean_file = output_dir / "silver_b_enriched.jsonl"
            quarantine_file = output_dir / "silver_b_quarantine.jsonl"

            with open(clean_file, "w", encoding="utf-8") as clean_out, \
                    open(quarantine_file, "w", encoding="utf-8") as quarantine_out:

                for record in records:
                    if record.get("quarantine_status", {}).get("is_corrupted"):
                        quarantine_out.write(json.dumps(record) + "\n")
                    else:
                        clean_out.write(json.dumps(record) + "\n")

            self._log(f"Saved clean production records to {clean_file}")
            self._log(f"Saved quarantined anomaly records to {quarantine_file}")

        except Exception as e:
            self._log(f"Failed to save split Silver-B files: {str(e)}")

    def get_stats(self) -> Dict[str, Any]:
        return self.stats
