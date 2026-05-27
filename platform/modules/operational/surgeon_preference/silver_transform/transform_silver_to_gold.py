"""
SURGEON PREFERENCE PIPELINE — SILVER → GOLD
Silver -> Gold ETL Pipeline with Standardisation + Gold Contract Validation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from typing import Any, Dict, Tuple

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from pydantic import ValidationError

from contracts.orthopaedic_preference_gold import OrthopaedicPreferenceGold

# =========================================================
# CONFIG
# =========================================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

SILVER_TABLE = "silver_cleaned.surgeon_preferences_clean"
GOLD_TABLE = "gold_analytics.surgeon_preferences_gold"
GOLD_ERROR_TABLE = "gold_errors.surgeon_preferences_errors"


# =========================================================
# DB CONFIG
# =========================================================
def get_database_config() -> Dict[str, str]:
    config = {
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "database": os.getenv("DB_NAME"),
    }
    missing = [k for k, v in config.items() if not v]
    if missing:
        raise EnvironmentError(f"Missing environment variables: {', '.join(missing)}")
    return config


def create_database_engine(config: Dict[str, str]) -> Engine:
    conn = (
        f"postgresql://{config['user']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{config['database']}"
    )
    engine = create_engine(conn)
    logger.info("Database engine created.")
    return engine


# =========================================================
# EXTRACT FROM SILVER
# =========================================================
def extract_silver_data(engine: Engine) -> pd.DataFrame:
    logger.info("Extracting silver layer data...")
    query = f"SELECT * FROM {SILVER_TABLE}"
    df = pd.read_sql(query, engine)
    logger.info(f"Extracted {len(df)} rows from silver layer.")
    return df


# =========================================================
# GOLD CONTRACT VALIDATION (STANDARDISATION)
# =========================================================
def validate_against_gold_contract(row: dict) -> Tuple[Dict[str, Any] | None, str | None]:
    """
    (clean_row_dict, None)  → valid
    (None, error_message)   → invalid
    """
    try:
        model = OrthopaedicPreferenceGold(**row)
        return model.model_dump(), None
    except ValidationError as e:
        return None, str(e)
    except Exception as e:
        return None, f"Unexpected error: {e}"


def apply_gold_validation(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    clean_rows = []
    error_rows = []

    for _, row in df.iterrows():
        row_dict = row.to_dict()

        clean, error = validate_against_gold_contract(row_dict)

        if error:
            row_dict["error"] = error
            error_rows.append(row_dict)
            if len(error_rows) == 1:
                logger.error(f"First Gold Validation Failure Sample: {error}")
        else:
            clean_rows.append(clean)

    return pd.DataFrame(clean_rows), pd.DataFrame(error_rows)


# =========================================================
# LOAD TO GOLD
# =========================================================
def load_to_gold(df: pd.DataFrame, engine: Engine) -> None:
    logger.info("Loading clean data into gold layer...")
    df.to_sql(
        name="surgeon_preferences_gold",
        con=engine,
        schema="gold_analytics",
        if_exists="replace",
        index=False,
    )
    logger.info(f"Successfully loaded {len(df)} clean rows into gold layer.")


def load_gold_errors(df: pd.DataFrame, engine: Engine) -> None:
    logger.info("Loading gold validation errors into gold_errors...")
    df.to_sql(
        name="surgeon_preferences_gold_errors",
        con=engine,
        schema="gold_errors",
        if_exists="replace",
        index=False,
    )
    logger.info(f"Successfully loaded {len(df)} error rows into gold_errors.")


# =========================================================
# MAIN PIPELINE
# =========================================================
def run_gold_pipeline() -> None:
    logger.info("Starting Silver → Gold surgeon preference pipeline...")

    config = get_database_config()
    engine = create_database_engine(config)

    silver_df = extract_silver_data(engine)

    clean_df, error_df = apply_gold_validation(silver_df)

    load_to_gold(clean_df, engine)
    load_gold_errors(error_df, engine)

    logger.info("Silver → Gold pipeline completed successfully.")


# =========================================================
# ENTRYPOINT
# =========================================================
if __name__ == "__main__":
    try:
        run_gold_pipeline()
    except Exception as error:
        logger.exception(f"Gold pipeline execution failed: {error}")
        raise
