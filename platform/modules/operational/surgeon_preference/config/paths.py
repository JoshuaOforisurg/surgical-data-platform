# config/paths.py

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

BRONZE_DIR = PROJECT_ROOT / "bronze_ingestion/storage/bronze_landing"
SILVER_A_DIR = PROJECT_ROOT / "silver_transform/data/silver_a_cleaned"