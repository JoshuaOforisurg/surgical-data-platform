"""
SURGEON PREFERENCE PIPELINE — PROFESSIONAL VERSION
Bronze -> Silver ETL Pipeline with Contract Validation
"""

# =========================================================
# IMPORTS
# =========================================================
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from pydantic import ValidationError
from contracts.silver_orthopaedic_preference import OrthopaedicPreference



# =========================================================
# CONFIGURATION
# =========================================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

DEFAULT_SPECIALITY = "Orthopaedics"

BRONZE_TABLE = "bronze_raw.surgeon_preferences"
SILVER_TABLE = "silver_cleaned.surgeon_preferences_clean"
ERROR_TABLE = "silver_errors.surgeon_preferences_errors"

REQUIRED_COLUMNS = [
    "surgeon_id",
    "surgeon_name",
    "speciality",
    "subspeciality",
    "procedure",
    "instrument",
    "preferred_retractor_size",
    "preferred_drill_brand",
    "needs_backup_suction",
    "years_of_experience",
    "hospital_affiliation",
    "generation_timestamp",
]

VALID_SUBSPECIALTIES = {
    "Joints", "Trauma", "Spine", "Paediatric", "Foot And Ankle"
}

RETRACTOR_SIZE_MAPPING = {
    "s": "Small",
    "small": "Small",
    "m": "Medium",
    "medium": "Medium",
    "l": "Large",
    "large": "Large",
    "xl": "Extra Large",
    "extra large": "Extra Large",
}

DRILL_BRAND_MAPPING = {
    "stryker": "Stryker",
    "depuy synthes": "Depuy Synthes",
    "arthrex v300": "Arthrex V300",
    "zimmer biomet": "Zimmer Biomet",
    "smith & nephew": "Smith & Nephew",
    "medtronic": "Medtronic",
}


# =========================================================
# DATABASE CONFIGURATION
# =========================================================
def get_database_config() -> Dict[str, str]:

    config = {
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "database": os.getenv("DB_NAME"),
    }

    missing = [key for key, value in config.items() if not value]

    if missing:
        raise EnvironmentError(
            f"Missing environment variables: {', '.join(missing)}"
        )

    return config


def create_database_engine(config: Dict[str, str]) -> Engine:

    connection_string = (
        f"postgresql://{config['user']}:{config['password']}@"
        f"{config['host']}:{config['port']}/{config['database']}"
    )

    engine = create_engine(connection_string)

    logger.info("Database engine created.")

    return engine


# =========================================================
# EXTRACTION
# =========================================================
def extract_bronze_data(engine: Engine) -> pd.DataFrame:

    logger.info("Extracting bronze layer data...")

    query = f"SELECT * FROM {BRONZE_TABLE}"

    df = pd.read_sql(query, engine)

    logger.info(f"Extracted {len(df)} rows from bronze layer.")

    return df


# =========================================================
# VALIDATION
# =========================================================
def validate_required_columns(df: pd.DataFrame) -> None:

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    logger.info("Required column validation passed.")


# =========================================================
# CLEANING FUNCTIONS
# =========================================================
def clean_string(value: Any) -> Optional[str]:

    if pd.isna(value):
        return None

    cleaned = str(value).strip()

    if cleaned == "" or cleaned.upper() == "N/A":
        return None

    return cleaned.title()


def extract_numeric(value: Any) -> Optional[int]:

    if pd.isna(value):
        return None

    if isinstance(value, list):

        if not value:
            return None

        value = value[0]

    digits = re.findall(r"\d+", str(value))

    return int(digits[0]) if digits else None


def clean_boolean(value: Any) -> Optional[bool]:

    if pd.isna(value):
        return None

    value = str(value).strip().lower()

    truthy = {"true", "yes", "y", "1"}
    falsy = {"false", "no", "n", "0"}

    if value in truthy:
        return True

    if value in falsy:
        return False

    return None


def clean_timestamp(value: Any) -> Optional[pd.Timestamp]:
    try:
        return pd.to_datetime(value, errors="coerce", dayfirst=True)
    except Exception:
        return None


def normalise_retractor_size(value: Any) -> Optional[str]:

    if pd.isna(value):
        return None

    cleaned = str(value).strip().lower()

    return RETRACTOR_SIZE_MAPPING.get(cleaned)


def normalise_drill_brand(value: Any) -> Optional[str]:

    if pd.isna(value):
        return None

    cleaned = str(value).strip().lower()

    return DRILL_BRAND_MAPPING.get(cleaned)


# =========================================================
# TRANSFORMATION
# =========================================================
def transform_data(df: pd.DataFrame) -> pd.DataFrame:

    logger.info("Starting transformation layer...")

    df = df.copy()

    # -----------------------------------------------------
    # STANDARDISE COLUMNS
    # -----------------------------------------------------
    df["surgeon_id"] = df["surgeon_id"].apply(extract_numeric)

    df["surgeon_name"] = df["surgeon_name"].apply(clean_string)

    df["speciality"] = DEFAULT_SPECIALITY

    df["subspeciality"] = df["subspeciality"].apply(clean_string)
    df["subspeciality"] = df["subspeciality"].apply(
        lambda x: x if x in VALID_SUBSPECIALTIES else None
    )

    df["procedure"] = df["procedure"].apply(clean_string)

    df["instrument"] = df["instrument"].apply(clean_string)

    df["preferred_retractor_size"] = df["preferred_retractor_size"].apply(
        normalise_retractor_size
    )

    df["preferred_drill_brand"] = df["preferred_drill_brand"].apply(
        normalise_drill_brand
    )

    df["needs_backup_suction"] = df["needs_backup_suction"].apply(clean_boolean)

    df["years_of_experience"] = df["years_of_experience"].apply(extract_numeric)

    df["hospital_affiliation"] = df["hospital_affiliation"].apply(clean_string)

    df["generation_timestamp"] = df["generation_timestamp"].apply(clean_timestamp)

    # -----------------------------------------------------
    # AUDIT COLUMNS
    # -----------------------------------------------------
    df["processed_at"] = pd.Timestamp.now('UTC')
    df["pipeline_version"] = "1.0"

    logger.info("Transformation layer completed.")

    return df


# =========================================================
# CONTRACT VALIDATION
# =========================================================
def validate_against_contract(row: dict):
    """
    Always returns a 2‑tuple:
    (clean_row_dict, None)  → valid
    (None, error_message)   → invalid
    """
    try:
        model = OrthopaedicPreference(**row)
        return model.dict(), None
    except ValidationError as e:
        return None, str(e)
    except Exception as e:
        # Catch ANY unexpected error and still return a tuple
        return None, f"Unexpected error: {e}"


def apply_contract_validation(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    clean_rows = []
    error_rows = []

    for _, row in df.iterrows():
        # CONVERT PANDAS NAN/NAT TO PYTHON NONE
        row_dict = {
            k: (None if pd.isna(v) else v)
            for k, v in row.to_dict().items()
        }

        clean, error = validate_against_contract(row_dict)

        if error:
            row_dict["error"] = error
            error_rows.append(row_dict)

            # Print the first error to terminal to diagnose other strict type issues
            if len(error_rows) == 1:
                logger.error(f"First Validation Failure Sample: {error}")
        else:
            clean_rows.append(clean)

    return pd.DataFrame(clean_rows), pd.DataFrame(error_rows)


# =========================================================
# LOAD TO SILVER
# =========================================================
def load_to_silver(df: pd.DataFrame, engine: Engine) -> None:

    logger.info("Loading clean data into silver layer...")

    df.to_sql(
        name="surgeon_preferences_clean",
        con=engine,
        schema="silver_cleaned",
        if_exists="replace",
        index=False,
    )

    logger.info(f"Successfully loaded {len(df)} clean rows into silver layer.")


def load_errors_to_silver(df: pd.DataFrame, engine: Engine) -> None:

    logger.info("Loading error rows into silver_errors...")

    df.to_sql(
        name="surgeon_preferences_errors",
        con=engine,
        schema="silver_errors",
        if_exists="replace",
        index=False,
    )

    logger.info(f"Successfully loaded {len(df)} error rows.")


# =========================================================
# MAIN PIPELINE
# =========================================================
def run_pipeline() -> None:

    logger.info("Starting surgeon preference pipeline...")

    config = get_database_config()
    engine = create_database_engine(config)

    raw_df = extract_bronze_data(engine)
    validate_required_columns(raw_df)

    transformed_df = transform_data(raw_df)

    clean_df, error_df = apply_contract_validation(transformed_df)

    load_to_silver(clean_df, engine)
    load_errors_to_silver(error_df, engine)

    logger.info("Pipeline completed successfully.")


# =========================================================
# ENTRYPOINT
# =========================================================
if __name__ == "__main__":

    try:
        run_pipeline()

    except Exception as error:

        logger.exception(
            f"Pipeline execution failed: {error}"
        )

        raise
