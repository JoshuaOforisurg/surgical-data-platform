import psycopg2
import pandas as pd
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def get_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        return psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT")
        )
    except psycopg2.Error as e:
        logger.error(f"Failed to connect to the database: {e}")
        raise

def load_to_postgres(
    df: pd.DataFrame,
    schema: str,
    table: str,
    batch_size: int = 1000,
    commit: bool = True
) -> None:
    """
    Loads a DataFrame into a specific schema.table in Postgres.

    Args:
        df: Pandas DataFrame to load.
        schema: Target schema name.
        table: Target table name.
        batch_size: Number of records to insert per batch (default: 1000).
        commit: Whether to commit the transaction (default: True).
    """
    if not (schema.isidentifier() and table.isidentifier()):
        raise ValueError("Invalid schema or table name")

    full_table_name = f"{schema}.{table}"
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        records = [tuple(x) for x in df.to_numpy()]
        columns = ",".join(df.columns)

        insert_query = f"""
            INSERT INTO {full_table_name} ({columns})
            VALUES %s
            ON CONFLICT DO NOTHING;
        """

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            execute_values(cursor, insert_query, batch)
            if commit:
                conn.commit()
            logger.info(f"Loaded batch of {len(batch)} records into {full_table_name}")

    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Error loading into {full_table_name}: {e}")
        raise

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
