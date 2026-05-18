import psycopg2
from psycopg2.extras import execute_batch
from typing import List, Dict, Any
from datetime import datetime, timezone


class PostgresLoader:
    """
    Loads normalised preference items into the bronze Postgres table.
    Maintains a single connection and uses batch inserts for performance.
    """

    def __init__(self, conn_string: str, batch_size: int = 500):
        self.conn_string = conn_string
        self.batch_size = batch_size
        self._buffer: List[Dict[str, Any]] = []

        # Open a single persistent connection for the entire pipeline lifecycle
        self._conn = psycopg2.connect(self.conn_string)

    def add(self, item: Dict[str, Any], source_file: str) -> None:
        """
        Add a normalised item to the batch buffer.
        """
        row = {
            **item,
            "source_file": source_file,
            "ingested_at": datetime.now(timezone.utc)  # Fixed: Modern timezone-aware UTC
        }
        self._buffer.append(row)

        if len(self._buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        """
        Write buffered rows to Postgres safely using a single transaction block.
        """
        if not self._buffer:
            return

        cur = self._conn.cursor()

        sql = """
            INSERT INTO bronze.surgeon_preference_items
            (surgeon_id, procedure_id, item_id, mandatory, quantity, notes, source_file, ingested_at)
            VALUES (%(surgeon_id)s, %(procedure_id)s, %(item_id)s, %(mandatory)s,
                    %(quantity)s, %(notes)s, %(source_file)s, %(ingested_at)s)
        """

        try:
            execute_batch(cur, sql, self._buffer)
            self._conn.commit()  # Save batch data cleanly
            self._buffer = []  # Clear buffer only after successful database save
        except Exception as e:
            self._conn.rollback()  # Crucial: Revert changes if database transaction crashes
            raise RuntimeError(f"Database batch insert failed: {str(e)}")
        finally:
            cur.close()

    def close(self) -> None:
        """
        Explicitly close the persistent database connection handle.
        """
        if self._conn and not self._conn.closed:
            self._conn.close()
