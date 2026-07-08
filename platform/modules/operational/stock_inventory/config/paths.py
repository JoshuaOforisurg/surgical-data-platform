from __future__ import annotations

from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_GENERATED_DIR = MODULE_ROOT / "synthetic_data" / "generated"
DATA_LAKE_DIR = MODULE_ROOT / "data_lake"
BRONZE_DIR = DATA_LAKE_DIR / "bronze"
BRONZE_RAW_DIR = BRONZE_DIR / "raw"
BRONZE_RECORDS_DIR = BRONZE_DIR / "records"
BRONZE_MANIFEST_DIR = BRONZE_DIR / "manifests"

