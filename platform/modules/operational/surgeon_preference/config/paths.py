from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_LAKE = BASE_DIR / "data_lake"

BRONZE_DIR = DATA_LAKE / "bronze"
SILVER_A_DIR = DATA_LAKE / "silver_a"
SILVER_B_DIR = DATA_LAKE / "silver_b"
GOLD_DIR = DATA_LAKE / "gold"

# ensure folders exist
for p in [BRONZE_DIR, SILVER_A_DIR, SILVER_B_DIR, GOLD_DIR]:
    p.mkdir(parents=True, exist_ok=True)