import psycopg2
from typing import Dict, Any, List


class DynamicMapper:
    def __init__(self, conn_string: str, target_table: str):
        self.conn_string = conn_string
        self.target_table = target_table
        self.db_columns = self._get_db_columns()
        # FIX: Keep lookups empty since you don't use auxiliary lookup tables
        self.lookups = {}

    def _get_db_columns(self) -> List[str]:
        """Reads the exact columns available in the database table."""
        if '.' in self.target_table:
            schema, table = self.target_table.split('.')
        else:
            schema, table = 'bronze_raw', self.target_table

        query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = %s 
              AND table_name = %s
            ORDER BY ordinal_position;
        """
        with psycopg2.connect(self.conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (schema, table))
                return [row[0] for row in cur.fetchall()]

    def transform_row(self, raw_row: Dict[str, Any]) -> Dict[str, Any]:
        """Maps raw fields directly to database columns."""
        transformed = {}
        for col in self.db_columns:
            # Directly map columns if they exist in your source CSV row
            if col in raw_row:
                transformed[col] = raw_row[col]
        return transformed


def insert_rows_to_db(conn_string: str, target_table: str, transformed_rows: List[Dict[str, Any]]) -> None:
    """Safely batches and writes transformed dictionary rows into the database."""
    if not transformed_rows:
        print("No rows found to insert.")
        return

    # 1. Extract the column names from the first row dictionary keys
    columns = transformed_rows[0].keys()

    # 2. Build a dynamic SQL statement: INSERT INTO bronze_raw.surgeon_preference_items (...) VALUES %s
    # Note: We safely quote the target table name here
    query = f"""
        INSERT INTO {target_table} ({', '.join(columns)}) 
        VALUES %s;
    """

    # 3. Convert list of dictionaries into a list of value tuples for psycopg2
    values = [tuple(row[col] for col in columns) for row in transformed_rows]

    try:
        with psycopg2.connect(conn_string) as conn:
            with conn.cursor() as cur:
                # execute_values is incredibly fast for handling batches like 500 rows
                execute_values(cur, query, values)

                # CRITICAL: This saves the data permanently to your database
                conn.commit()

                print(f"Successfully wrote {len(transformed_rows)} rows to {target_table}!")

    except Exception as e:
        print(f"Database write failed: {e}")