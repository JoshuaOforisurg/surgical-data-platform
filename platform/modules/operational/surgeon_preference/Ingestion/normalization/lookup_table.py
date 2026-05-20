import psycopg2
from typing import Dict, Any, List


class DynamicMapper:
    def __init__(self, conn_string: str, target_table: str):
        self.conn_string = conn_string
        self.target_table = target_table  # e.g., "public.preference_items"
        self.db_columns = self._get_db_columns()
        self.lookups = self._build_dynamic_lookups()

    def _get_db_columns(self) -> List[str]:
        """Reads the exact columns available in the database table."""
        schema, table = self.target_table.split('.') if '.' in self.target_table else ('bronze_raw', self.target_table)
        query = """
            SELECT *
            FROM bronze_raw.surgeon_preference_items 
            WHERE schema= bronze_raw AND table= surgeon_preference_items;
        """
        schema = "bronze_raw"
        table = "surgeon_preference_items"
        with psycopg2.connect(self.conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (schema, table))
                return [row[0] for row in cur.fetchall()]

    def _build_dynamic_lookups(self) -> Dict[str, Dict[str, Any]]:
        """Maps relationship suffixes automatically based on naming conventions."""
        lookups = {}
        # Find ID columns that imply a lookup table (e.g., surgeon_id -> metadata.surgeons)
        for col in self.db_columns:
            if col.endswith("_id"):
                entity = col.replace("_id", "")  # "surgeon"
                # Assumes standard convention: metadata.surgeons table, surgeon_name, surgeon_id
                lookups[col] = self._fetch_map(
                    table=f"bronze_raw.{entity}s",
                    name_col=f"{entity}_name",
                    id_col=col
                )
        return lookups

    def _fetch_map(self, table: str, name_col: str, id_col: str) -> Dict[str, Any]:
        """Fetches key-value pairs for lookups dynamically."""
        query = f"SELECT lower({name_col}), {id_col} FROM {table};"
        try:
            with psycopg2.connect(self.conn_string) as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    return {str(row[0]).strip(): row[1] for row in cur.fetchall()}
        except Exception:
            return {}  # Fallback if metadata table doesn't exist

    def transform_row(self, raw_row: Dict[str, Any]) -> Dict[str, Any]:
        """Maps raw fields to database columns dynamically."""
        transformed = {}

        for col in self.db_columns:
            # Type 1: Foreign key lookups (e.g., target wants surgeon_id, source has surgeon_name)
            if col in self.lookups:
                source_key = col.replace("_id", "_name")
                raw_val = str(raw_row.get(source_key, "")).strip().lower()
                transformed[col] = self.lookups[col].get(raw_val)

            # Type 2: Directly mapped columns (e.g., notes, quantity)
            elif col in raw_row:
                val = raw_row[col]
                # Optional: Add data type casting logic here based on column type if needed
                transformed[col] = val

        return transformed
