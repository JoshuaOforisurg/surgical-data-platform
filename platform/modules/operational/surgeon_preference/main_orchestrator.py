from typing import List, Dict, Any, Optional
import logging
import traceback
from datetime import datetime, UTC

class UnifiedIngestionPipeline:
    """
    Orchestrates full data flow:
    Raw → Silver A → Silver B → Silver C → Gold

    Design goals:
    - Stage isolation (fail-safe per record)
    - Zero silent data drops (unhandled exceptions go to quarantine)
    - Full lineage and traceability
    """

    def __init__(self, silver_a, silver_b, silver_c, gold, logger: Optional[logging.Logger] = None):
        self.silver_a = silver_a
        self.silver_b = silver_b
        self.silver_c = silver_c
        self.gold = gold
        self.logger = logger or logging.getLogger(__name__)

    def _safe_execute(self, stage_name: str, func, input_data: Any) -> tuple[Optional[Any], Optional[str]]:
        try:
            return func(input_data), None
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.logger.error(f"[{stage_name}] failed: {error_msg}")
            return None, f"[{stage_name}_EXCEPTION] {str(e)}"

    def run(self, raw_records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        production_pool = []
        quarantine_pool = []

        self.logger.info(f"Starting pipeline execution for {len(raw_records)} records.")

        for idx, raw in enumerate(raw_records):
            record_errors = []
            is_quarantined = False
            quarantine_reason = None

            # -------------------------
            # SILVER A (Basic Cleaning)
            # -------------------------
            # FIX: Properly structure input to match the SilverTransformer definition
            silver_a_wrapped = {"metadata": {"file_name": "stream_input"}, "content": raw}
            silver_a, err = self._safe_execute("SILVER_A", self.silver_a.flatten_card, silver_a_wrapped)
            if err:
                record_errors.append(err)
                is_quarantined = True
                quarantine_reason = "SILVER_A_CRASH"
                silver_a = {"content": raw}

            # -------------------------
            # SILVER B (Clinical Enrichment & Quantity Check)
            # -------------------------
            silver_b, err = self._safe_execute("SILVER_B", self.silver_b.enrich, silver_a)
            if err:
                record_errors.append(err)
                is_quarantined = True
                quarantine_reason = "SILVER_B_CRASH"
                silver_b = silver_a.copy()
            else:
                b_quarantine_status = silver_b.get("quarantine_status", {})
                if b_quarantine_status.get("is_corrupted"):
                    is_quarantined = True
                    quarantine_reason = b_quarantine_status.get("quarantine_reason", "CLINICAL_ANOMALY")

            # -------------------------
            # SILVER C (Optional Step)
            # -------------------------
            silver_c, err = self._safe_execute("SILVER_C", self.silver_c.process, silver_b)
            if err or silver_c is None:
                if err:
                    record_errors.append(err)
                silver_c = silver_b

            # -------------------------
            # GOLD LAYER (Aggregation / Materialisation)
            # -------------------------
            gold, err = self._safe_execute("GOLD", self.gold.aggregate, silver_c)
            if err:
                record_errors.append(err)
                is_quarantined = True
                quarantine_reason = "GOLD_CRASH"
                gold = silver_c.copy()

            # -------------------------
            # LINEAGE AND ROUTING
            # -------------------------
            gold["_pipeline_metadata"] = {
                "record_index": idx,
                "processed_at": datetime.now(UTC).isoformat(),
                "is_quarantined": is_quarantined,
                "quarantine_reason": quarantine_reason,
                "pipeline_errors": record_errors,
                "silver_a_success": "SILVER_A_CRASH" not in "".join(record_errors),
                "silver_b_success": "SILVER_B_CRASH" not in "".join(record_errors),
            }

            if is_quarantined:
                quarantine_pool.append(gold)
            else:
                production_pool.append(gold)

        self.logger.info(
            f"Pipeline Complete | Total: {len(raw_records)} | "
            f"Production: {len(production_pool)} | Quarantined: {len(quarantine_pool)}"
        )

        return {
            "production": production_pool,
            "quarantine": quarantine_pool
        }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    class FallbackSilverC:
        def process(self, record): return record

    class FallbackGold:
        def aggregate(self, record): return record

    from silver_transform.silver_a.silver_a_transformer import SilverTransformer
    from silver_transform.silver_b.clinical_enrichment import ClinicalEnrichmentEngine

    sa = SilverTransformer()
    sb = ClinicalEnrichmentEngine()
    sc = FallbackSilverC()
    g = FallbackGold()

    pipeline = UnifiedIngestionPipeline(silver_a=sa, silver_b=sb, silver_c=sc, gold=g)

    mock_bronze_records = [
        {
            "surgeon": {"full_name": "  MR JOHN SMITH ", "glove_size": "7.5"},
            "procedure_name": "total hip replacement",
            "instruments": '[{"name": "S&N R3 Main Instrument Set", "quantity": 1}]'
        },
        {
            "surgeon": {"full_name": " Dr Jane Doe "},
            "procedure_name": "total knee replacement",
            "instruments": '[{"name": "Journey II Spacer Set", "quantity": -1}]'
        }
    ]

    output_pools = pipeline.run(mock_bronze_records)
    print(f"\n--- EXECUTION OUTPUT ---")
    print(f"Production Pool Size: {len(output_pools['production'])}")
    print(f"Quarantine Pool Size:  {len(output_pools['quarantine'])}")
