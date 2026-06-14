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
from gold_cleaned.operational_preference_card import OperationalPreferenceGoldBuilder

from config.paths import GOLD_DIR

class SurgicalDataPipeline:
    def __init__(self):
        self.silver_a = SilverTransformer()
        self.silver_b = SilverBBatchEnricher()
        self.operational_gold = OperationalPreferenceGoldBuilder()
        self.analytics_gold = ClinicalGoldAnalytics()

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
    def run_operational_gold(self, silver_b_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        print("[PIPELINE] Running operational Gold preference cards...")
        return self.operational_gold.build_and_write(silver_b_data)

    def run_analytics_gold(self, silver_b_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        print("[PIPELINE] Running analytical Gold report...")
        report = self.analytics_gold.full_report(silver_b_data)
        output_file = GOLD_DIR / "gold_analytics_report.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return {"report": report, "path": output_file}

    # -----------------------------------------------------
    # FULL PIPELINE EXECUTION
    # -----------------------------------------------------
    def run(self, bronze_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        start_time = datetime.now(UTC)

        # Step 1: Silver-A
        silver_a_data = self.run_silver_a(bronze_data)

        # Step 2: Silver-B
        silver_b_data = self.run_silver_b(silver_a_data)

        # Step 3: Operational Gold for frontline Streamlit
        operational_gold = self.run_operational_gold(silver_b_data)

        # Step 4: Analytical Gold snapshot for future cost/usage work
        analytics_gold = self.run_analytics_gold(silver_b_data)

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
            "gold_operational": operational_gold,
            "gold_analytics": analytics_gold,
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

    # Save the full run metadata to a file (optional)
    output_file = GOLD_DIR / "pipeline_run.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\nPipeline result saved to: {output_file}")
