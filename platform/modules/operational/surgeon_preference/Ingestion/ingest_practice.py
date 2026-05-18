"""
ETL ingestion pipeline for orthopaedic surgeon preference data.
Handles messy synthetic data with missing values.
No transformations or validation are applied.

Pipeline Steps:
1. Read CSV (no transformations)
2. Load all rows into PostgreSQL (missing values allowed)
3. Log errors only for unreadable rows

Key Features:
- All fields treated as text (no validation)
- Missing values allowed (None, empty strings, NaN)
- No transformations or coercion
"""

import logging
import os
from typing import List, Optional

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql
from psycopg2.pool import SimpleConnectionPool
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Connection pool setup

DB_POOL=SimpleConnectionPool(

# Create and return a PostgreSQL database connection using .env variables.

        minconn=1,
        maxconn=5,
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
    )
# ---------------------------------------------------------
# Pydantic Schema (No Validation, All Fields Optional)
# ---------------------------------------------------------
class OrthopaedicPreference(BaseModel):

    surgeon_id: Optional[str] = None
    surgeon_name: Optional[str] = None
    speciality: Optional[str] = None
    subspecialty: Optional[str] = None
    procedure: Optional[str] = None
    instrument: Optional[str] = None
    preferred_retractor_size: Optional[str] = None
    preferred_drill_brand: Optional[str] = None
    needs_backup_suction: Optional[str] = None
    years_of_experience: Optional[str] = None
    hospital_affiliation: Optional[str] = None
    generation_timestamp: Optional[str] = None

    class Config:
        from_attributes = True

# ---------------------------------------------------------
# Ingestion (Extract + No Validation)
# ---------------------------------------------------------
def ingest_csv(path: str) -> tuple[List[dict], int]:
    """
    Read a CSV file and return all rows as dictionaries.
    No validation or transformations are applied.

    Args:
        path: Path to the CSV file.

    Returns:
        tuple: (list_of_rows, error_count)

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        pd.errors.EmptyDataError: If the CSV file is empty.
        Exception: For other unexpected errors during CSV reading.
    """
    logger.info(f"Reading CSV from: {path}")
    try:
        df = pd.read_csv(path)
    except FileNotFoundError as e:
        logger.error(f"CSV file not found: {e}")
        raise
    except pd.errors.EmptyDataError as e:
        logger.error(f"CSV file is empty: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to read CSV file: {e}")
        raise

    # Convert all rows to dictionaries (missing values are preserved as None/NaN)
    records = df.to_dict("records")
    errors = 0

    logger.info(f"Successfully read {len(records)} rows from CSV.")
    return records, errors

# ---------------------------------------------------------
# Load to Postgres
# ---------------------------------------------------------
def load_to_postgres(records: List[dict]) -> int:
    """
    Load records into PostgreSQL staging table.
    No validation or transformations are applied.

    Args:
        records: List of dictionaries (rows) to load.

    Returns:
        int: Number of records successfully inserted.
    """
    logger.info("Connecting to PostgreSQL...")
    conn = None
    cur = None
    inserted_count = 0

    if not records:
        logger.warning("No records to insert. Skipping database load.")
        return inserted_count

    try:
        conn = DB_POOL.getconn()
        cur = conn.cursor()

        # Add the name of the table in your schema and it's contents here
        insert_sql = sql.SQL("""
            INSERT INTO bronze_schema (  
                surgeon_id, surgeon_name, speciality, subspeciality,
                procedure, instrument, preferred_retractor_size,
                preferred_drill_brand, needs_backup_suction,
                years_of_experience, hospital_affiliation,
                generation_timestamp
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """)

        # Batch insertion for performance
        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            batch_data = [
                (
                    row.get("surgeon_id"),
                    row.get("surgeon_name"),
                    row.get("speciality"),
                    row.get("subspecialty"),
                    row.get("procedure"),
                    row.get("instrument"),
                    row.get("preferred_retractor_size"),
                    row.get("preferred_drill_brand"),
                    row.get("needs_backup_suction"),
                    row.get("years_of_experience"),
                    row.get("hospital_affiliation"),
                    row.get("generation_timestamp"),
                )
                for row in batch
            ]
            cur.executemany(insert_sql, batch_data)
            inserted_count += len(batch)
            logger.info(f"Inserted batch {i//batch_size + 1}: {len(batch)} records")

        conn.commit()
        logger.info(f"Successfully inserted {inserted_count} records into PostgreSQL.")

    except psycopg2.Error as e:
        logger.error(f"Failed to insert records into PostgreSQL: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            DB_POOL.putconn(conn)

    return inserted_count

# ---------------------------------------------------------
# Pipeline Runner
# ---------------------------------------------------------
def run_pipeline(csv_path: Optional[str] = None) -> None:
    """
    Run the complete ETL ingestion pipeline.

    Args:
        csv_path: Path to the CSV file. If None, uses default path.
    """
    csv_path = csv_path  # add your file path here

    logger.info("Starting surgeon preference ETL ingestion pipeline...")
    try:
        records, errors = ingest_csv(csv_path)
        if not records:
            logger.warning("No rows to insert. Pipeline aborted.")
            return

        inserted_count = load_to_postgres(records)
        logger.info(
            f"Pipeline completed successfully. "
            f"Read: {len(records)}, Inserted: {inserted_count}, Errors: {errors}"
        )

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise

def close_pool() -> None:
    """Close all connections in the PostgreSQL connection pool."""
    DB_POOL.closeall()
    logger.info("PostgreSQL connection pool closed.")

if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as e:
        logger.critical(f"Pipeline crashed: {e}")
        raise
    finally:
        close_pool()
