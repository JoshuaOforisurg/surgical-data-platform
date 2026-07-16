from __future__ import annotations

from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_GENERATED_DIR = MODULE_ROOT / "synthetic_data" / "generated"
DATA_LAKE_DIR = MODULE_ROOT / "data_lake"
BRONZE_DIR = DATA_LAKE_DIR / "bronze"
BRONZE_RAW_DIR = BRONZE_DIR / "raw"
BRONZE_RECORDS_DIR = BRONZE_DIR / "records"
BRONZE_MANIFEST_DIR = BRONZE_DIR / "manifests"
SILVER_A_DIR = DATA_LAKE_DIR / "silver_a"
SILVER_A_RECORDS_DIR = SILVER_A_DIR / "records"
SILVER_A_MANIFEST_DIR = SILVER_A_DIR / "manifests"
SILVER_B_DIR = DATA_LAKE_DIR / "silver_b"
SILVER_B_RECORDS_DIR = SILVER_B_DIR / "records"
SILVER_B_MANIFEST_DIR = SILVER_B_DIR / "manifests"
GOLD_DIR = DATA_LAKE_DIR / "gold"
GOLD_RECORDS_DIR = GOLD_DIR / "records"
GOLD_MANIFEST_DIR = GOLD_DIR / "manifests"
PIPELINE_MANIFEST_DIR = DATA_LAKE_DIR / "pipeline_manifests"
