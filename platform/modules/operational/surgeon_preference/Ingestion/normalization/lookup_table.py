# normalisation/lookup_tables.py
import os
import psycopg2
from typing import Dict

# 1. Grab your database connection string directly from your pipeline configuration
CONN_STRING = os.getenv("PREF_PIPELINE_PG_CONN", "")

def fetch_lookup_map(table_name: str, name_col: str, id_col: str) -> Dict[str, int]:
    """
    Dynamically fetches the latest Faker-generated master rows from Postgres.
    """
    if not CONN_STRING:
        # Fallback to an empty map during quick unit testing if env isn't set
        return {}

    lookup_map = {}
    try:
        with psycopg2.connect(CONN_STRING) as conn:
            with conn.cursor() as cur:
                # Dynamically fetch the names and integer primary keys
                cur.execute(f"SELECT LOWER(TRIM({name_col})), {id_col} FROM {table_name}")
                for row in cur.fetchall():
                    if row[0]:  # Ensure name key isn't null
                        lookup_map[row[0]] = row[1]
    except Exception as e:
        print(f"Warning: Could not build dynamic dynamic lookup map for {table_name}. Error: {e}")

    return lookup_map


# 2. These maps automatically populate themselves when your pipeline script starts!
SURGEON_MAP = fetch_lookup_map("metadata.surgeons", "surgeon_name", "surgeon_id")
PROCEDURE_MAP = fetch_lookup_map("metadata.procedures", "procedure_name", "procedure_id")
INSTRUMENT_MAP = fetch_lookup_map("metadata.instruments", "item_name", "item_id")
