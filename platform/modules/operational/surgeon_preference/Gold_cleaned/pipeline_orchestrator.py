from typing import List, Dict, Any
from datetime import datetime, UTC
import json
from pathlib import Path

# -------------------------
# SILVER-A
# -------------------------
from silver_transform.silver_a.silver_a_transformer import SilverTransformer

# -------------------------
# SILVER-B
# -------------------------
from silver_transform.silver_b.silver_b_batch_enricher import SilverBBatchEnricher

# -------------------------
# GOLD
# -------------------------
from gold_cleaned.clinical_analytics import ClinicalGoldAnalytics

from config.paths import GOLD_DIR

class SurgicalDataPipeline:
    def __init__(self):
        self.silver_a = SilverTransformer()
        self.silver_b = SilverBBatchEnricher()
        self.gold = ClinicalGoldAnalytics()

    # -----------------------------------------------------
    # BRONZE → SILVER-A
    # -----------------------------------------------------
    def run_silver_a(self, bronze_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.silver_a.transform_records(bronze_data)

    # -----------------------------------------------------
    # SILVER-A → SILVER-B
    # -----------------------------------------------------
    def run_silver_b(self, silver_a_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        print("[PIPELINE] Running Silver-B enrichment...")
        return self.silver_b.process(silver_a_data)

    # -----------------------------------------------------
    # SILVER-B → GOLD
    # -----------------------------------------------------
    def run_gold(self, silver_b_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        print("[PIPELINE] Running Gold analytics...")
        return self.gold.full_report(silver_b_data)

    # -----------------------------------------------------
    # FULL PIPELINE EXECUTION
    # -----------------------------------------------------
    def run(self, bronze_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        start_time = datetime.now(UTC)

        # Step 1: Silver-A
        silver_a_data = self.run_silver_a(bronze_data)

        # Step 2: Silver-B
        silver_b_data = self.run_silver_b(silver_a_data)

        # Step 3: Gold Analytics
        gold_report = self.run_gold(silver_b_data)

        end_time = datetime.now(UTC)
        duration = (end_time - start_time).total_seconds()

        print(f"[PIPELINE] Completed in {duration:.2f} seconds")

        return {
            "pipeline_metadata": {
                "started_at": start_time.isoformat(),
                "completed_at": end_time.isoformat(),
                "duration_seconds": duration,
                "records_processed": len(bronze_data),
            },
            "silver_a_output": silver_a_data,
            "silver_b_output": silver_b_data,
            "gold_report": gold_report,
        }

# =========================================================
# OPTIONAL ENTRY POINT
# =========================================================

if __name__ == "__main__":
    # Example placeholder (replace with real bronze loader)
    sample_bronze_data = [
        {
            "surgeon": {"full_name": "Dr Smith"},
            "procedure": "total knee replacement",
            "instrument_system": "journey knee",
            "implants": ["Journey II BCS Femoral Component"],
            "instruments": ["Journey II Spacer Set"],
        }
    ]

    pipeline = SurgicalDataPipeline()
    result = pipeline.run(sample_bronze_data)

    print("\nPIPELINE COMPLETE")
    print(result["pipeline_metadata"])

    # Save the result to a file (optional)
    output_file = GOLD_DIR / "clinical_report.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists

    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nPipeline result saved to: {output_file}")
