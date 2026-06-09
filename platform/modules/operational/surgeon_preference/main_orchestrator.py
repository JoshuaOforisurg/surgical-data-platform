from typing import List, Dict, Any, Optional, Tuple
import os
import json
import logging
import traceback
import re
from datetime import datetime, UTC

import boto3
from boto3.session import Session
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()


# ----------------------------
# SECURITY UTILITIES
# ----------------------------

def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def safe_record_id(value: Optional[str], fallback: str) -> str:
    value = (value or fallback).strip().lower()
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:80]


class SafeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return str(obj)
        except Exception:
            return None


MAX_RECORD_SIZE_BYTES = 5_000_000  # 5MB limit per object


# ----------------------------
# PIPELINE
# ----------------------------

class UnifiedIngestionPipeline:
    """
    Secure orchestrated pipeline:
    Raw → Silver A → Silver B → Silver C → Gold
    """

    def __init__(self, silver_a, silver_b, silver_c, gold, logger: Optional[logging.Logger] = None):
        self.silver_a = silver_a
        self.silver_b = silver_b
        self.silver_c = silver_c
        self.gold = gold
        self.logger = logger or logging.getLogger(__name__)

        # Secure MinIO / S3 client (no defaults allowed)
        endpoint = require_env("MINIO_ENDPOINT")
        access_key = require_env("MINIO_ACCESS_KEY")
        secret_key = require_env("MINIO_SECRET_KEY")

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=f"http://{endpoint}",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            verify=True,
            config=Config(signature_version="s3v4")
        )

        self._initialize_minio_buckets()

    # ----------------------------
    # STORAGE INITIALISATION
    # ----------------------------

    def _initialize_minio_buckets(self):
        buckets = ["bronze", "silver", "gold", "quarantine"]

        for bucket in buckets:
            try:
                self.s3_client.head_bucket(Bucket=bucket)
            except Exception:
                self.s3_client.create_bucket(Bucket=bucket)
                self.logger.info(f"Created missing bucket: {bucket}")

    # ----------------------------
    # SAFE STORAGE
    # ----------------------------

    def _save_to_minio(self, bucket: str, key: str, data: Any):
        try:
            payload = json.dumps(data, cls=SafeJSONEncoder)

            if len(payload.encode("utf-8")) > MAX_RECORD_SIZE_BYTES:
                raise ValueError(f"Payload too large for storage: {key}")

            self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=payload,
                ContentType="application/json"
            )

        except Exception:
            self.logger.exception(f"MinIO write failed [{bucket}] key={key}")
            raise  # DO NOT silently ignore

    # ----------------------------
    # SAFE EXECUTION WRAPPER
    # ----------------------------

    def _safe_execute(self, stage_name: str, func, input_data: Any) -> Tuple[Optional[Any], Optional[str]]:
        try:
            return func(input_data), None
        except Exception as e:
            error = f"{stage_name}: {str(e)}"
            self.logger.error(f"{error}\n{traceback.format_exc()}")
            return None, error

    # ----------------------------
    # PIPELINE RUN
    # ----------------------------

    def run(self, raw_records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        production_pool = []
        quarantine_pool = []

        run_ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

        self.logger.info(f"Pipeline started. Records={len(raw_records)}")

        # Store raw bronze snapshot
        self._save_to_minio("bronze", f"run_{run_ts}/raw_batch.json", raw_records)

        for idx, raw in enumerate(raw_records):
            errors = []
            quarantined = False
            reason = None

            record_id = safe_record_id(
                raw.get("surgeon", {}).get("full_name"),
                f"index_{idx}"
            )

            # ---------------- SILVER A ----------------
            silver_a_input = {"metadata": {"source": "stream"}, "content": raw}
            silver_a, err = self._safe_execute("SILVER_A", self.silver_a.flatten_card, silver_a_input)

            if err:
                errors.append(err)
                quarantined = True
                reason = "SILVER_A_FAILURE"
                silver_a = {"content": raw}

            # ---------------- SILVER B ----------------
            silver_b, err = self._safe_execute("SILVER_B", self.silver_b.enrich, silver_a)

            if err:
                errors.append(err)
                quarantined = True
                reason = reason or "SILVER_B_FAILURE"
                silver_b = silver_a
            else:
                if silver_b.get("quarantine_status", {}).get("is_corrupted"):
                    quarantined = True
                    reason = silver_b["quarantine_status"].get("reason", "DATA_ANOMALY")

            # ---------------- SILVER C ----------------
            silver_c, err = self._safe_execute("SILVER_C", self.silver_c.process, silver_b)
            if err:
                errors.append(err)
                silver_c = silver_b

            # Save silver layer snapshot
            self._save_to_minio(
                "silver",
                f"run_{run_ts}/{record_id}_silver.json",
                silver_c
            )

            # ---------------- GOLD ----------------
            gold, err = self._safe_execute("GOLD", self.gold.aggregate, silver_c)

            if err:
                errors.append(err)
                quarantined = True
                reason = reason or "GOLD_FAILURE"
                gold = silver_c

            # ---------------- LINEAGE ----------------
            gold["_pipeline_metadata"] = {
                "record_index": idx,
                "record_id": record_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "quarantined": quarantined,
                "reason": reason,
                "errors": errors
            }

            # ---------------- ROUTING ----------------
            if quarantined:
                quarantine_pool.append(gold)
                self._save_to_minio(
                    "quarantine",
                    f"run_{run_ts}/{record_id}_quarantine.json",
                    gold
                )
            else:
                production_pool.append(gold)
                self._save_to_minio(
                    "gold",
                    f"run_{run_ts}/{record_id}_gold.json",
                    gold
                )

        self.logger.info(
            f"Pipeline complete | total={len(raw_records)} "
            f"prod={len(production_pool)} quarantine={len(quarantine_pool)}"
        )

        return {
            "production": production_pool,
            "quarantine": quarantine_pool
        }


# ----------------------------
# TEST HARNESS
# ----------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    class FallbackSilverC:
        def process(self, record): return record

    class FallbackGold:
        def aggregate(self, record): return record

    from silver_transform.silver_a.silver_a_transformer import SilverTransformer
    from silver_transform.silver_b.clinical_enrichment import ClinicalEnrichmentEngine

    pipeline = UnifiedIngestionPipeline(
        silver_a=SilverTransformer(),
        silver_b=ClinicalEnrichmentEngine(),
        silver_c=FallbackSilverC(),
        gold=FallbackGold()
    )

    mock_data = [
        {
            "surgeon": {"full_name": " MR JOHN SMITH "},
            "procedure_name": "total hip replacement"
        },
        {
            "surgeon": {"full_name": " Dr Jane Doe "},
            "procedure_name": "total knee replacement"
        }
    ]

    result = pipeline.run(mock_data)

    print("\n--- OUTPUT ---")
    print("Production:", len(result["production"]))
    print("Quarantine:", len(result["quarantine"]))