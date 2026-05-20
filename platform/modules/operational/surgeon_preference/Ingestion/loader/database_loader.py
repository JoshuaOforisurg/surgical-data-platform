import psycopg2
from psycopg2.extras import execute_values
from typing import List, Dict, Any
from datetime import datetime, timezone


class PostgresLoader:
    """
    Batch loader for normalised surgeon preference items.
    Designed for reliable ingestion into bronze layer.
    """

    def __init__(self, conn_string: str, batch_size: int = 500):
        self.conn_string = conn_string
        self.batch_size = batch_size

        self._buffer: List[Dict[str, Any]] = []
        self._conn = None

    def _connect(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.conn_string)

    def add(self, item: Dict[str, Any], source_file: str) -> None:
        """
        Add item to buffer and flush when threshold reached.
        """

        row = {
            **item,
            "source_file": source_file,
            "ingested_at": datetime.now(timezone.utc)
        }

        self._buffer.append(row)

        if len(self._buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        """
        Flush buffer into Postgres in a single transaction.
        """

        if not self._buffer:
            return

        self._connect()
        cur = self._conn.cursor()

        try:
            values = [
                (
                    r["surgeon_id"],
                    r["procedure_id"],
                    r["item_id"],
                    r["mandatory"],
                    r["quantity"],
                    r.get("notes"),
                    r["source_file"],
                    r["ingested_at"],
                )
                for r in self._buffer
            ]

            sql = """
                INSERT INTO bronze_raw.surgeon_preference_items
                (surgeon_id, procedure_id, item_id, mandatory,
                 quantity, notes, source_file, ingested_at)
                VALUES %s
            """

            execute_values(cur, sql, values)

            self._conn.commit()
            self._buffer.clear()

        except Exception as e:
            self._conn.rollback()
            raise RuntimeError(f"Database batch insert failed: {e}")

        finally:
            cur.close()

    def close(self) -> None:
        """
        Flush remaining records and close connection.
        """

        try:
            self.flush()
        finally:
            if self._conn and not self._conn.closed:
                self._conn.close()