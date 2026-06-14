from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import psycopg2
from psycopg2.extras import Json, execute_values

from config.settings import PostgresSettings


LOGGER = logging.getLogger(__name__)


class BronzeCatalogRepository:
    """
    Postgres-backed bronze ledger.

    Raw bytes live in MinIO. Postgres stores lifecycle metadata, raw record
    payloads, and the audit trail. When pyiceberg is installed, the pipeline can
    also bootstrap an Iceberg SQL catalog using the same Postgres service.
    """

    def __init__(self, settings: Optional[PostgresSettings]):
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return self.settings is not None

    def initialise(self) -> None:
        if not self.enabled:
            LOGGER.warning("Postgres settings missing; bronze catalog writes are disabled.")
            return

        statements = [
            "CREATE SCHEMA IF NOT EXISTS bronze_raw",
            "CREATE SCHEMA IF NOT EXISTS pipeline_audit",
            """
            CREATE TABLE IF NOT EXISTS bronze_raw.ingested_files (
                file_id UUID PRIMARY KEY,
                run_id TEXT NOT NULL,
                bucket TEXT NOT NULL,
                object_key TEXT NOT NULL,
                object_uri TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_extension TEXT NOT NULL,
                content_type TEXT,
                size_bytes BIGINT,
                checksum_sha256 TEXT,
                status TEXT NOT NULL DEFAULT 'landed',
                record_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bronze_raw.ingested_records (
                record_id UUID PRIMARY KEY,
                file_id UUID REFERENCES bronze_raw.ingested_files(file_id),
                run_id TEXT NOT NULL,
                record_ordinal INTEGER NOT NULL,
                raw_payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS pipeline_audit.pipeline_runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                source_path TEXT,
                files_landed INTEGER NOT NULL DEFAULT 0,
                records_processed INTEGER NOT NULL DEFAULT 0,
                gold_operational_key TEXT,
                gold_analytics_key TEXT,
                error_message TEXT,
                started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMPTZ
            )
            """,
        ]

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
            conn.commit()

    def bootstrap_iceberg_catalog(self, warehouse_uri: str) -> None:
        if not self.enabled:
            return

        try:
            from pyiceberg.catalog import load_catalog
            from pyiceberg.exceptions import NoSuchNamespaceError
        except Exception:
            LOGGER.warning("pyiceberg is not installed; skipping Iceberg catalog bootstrap.")
            return

        try:
            catalog = load_catalog(
                "surgeon_preference",
                **{
                    "type": "sql",
                    "uri": self.settings.sqlalchemy_uri,
                    "warehouse": warehouse_uri,
                },
            )
            try:
                catalog.load_namespace_properties("bronze_raw")
            except NoSuchNamespaceError:
                catalog.create_namespace("bronze_raw")
            LOGGER.info("Iceberg SQL catalog is available with warehouse=%s", warehouse_uri)
        except Exception:
            LOGGER.exception("Iceberg catalog bootstrap failed; Postgres bronze ledger remains available.")

    def start_run(self, run_id: str, source_path: str) -> None:
        if not self.enabled:
            return
        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pipeline_audit.pipeline_runs (run_id, status, source_path)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (run_id)
                    DO UPDATE SET status = EXCLUDED.status, source_path = EXCLUDED.source_path
                    """,
                    (run_id, "running", source_path),
                )
            conn.commit()

    def register_file(self, metadata: Dict[str, Any]) -> uuid.UUID:
        file_id = uuid.uuid4()
        if not self.enabled:
            return file_id

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bronze_raw.ingested_files (
                        file_id, run_id, bucket, object_key, object_uri,
                        original_filename, file_extension, content_type,
                        size_bytes, checksum_sha256, status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(file_id),
                        metadata["run_id"],
                        metadata["bucket"],
                        metadata["object_key"],
                        metadata["object_uri"],
                        metadata["original_filename"],
                        metadata["file_extension"],
                        metadata.get("content_type"),
                        metadata.get("size_bytes"),
                        metadata.get("checksum_sha256"),
                        "landed",
                    ),
                )
            conn.commit()
        return file_id

    def write_records(
        self,
        file_id: uuid.UUID,
        run_id: str,
        records: Iterable[Dict[str, Any]],
    ) -> int:
        records = list(records)
        if not self.enabled:
            return len(records)

        values = [
            (str(uuid.uuid4()), str(file_id), run_id, idx, Json(record))
            for idx, record in enumerate(records, start=1)
        ]
        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                if values:
                    execute_values(
                        cur,
                        """
                        INSERT INTO bronze_raw.ingested_records (
                            record_id, file_id, run_id, record_ordinal, raw_payload
                        )
                        VALUES %s
                        """,
                        values,
                    )
                cur.execute(
                    """
                    UPDATE bronze_raw.ingested_files
                    SET record_count = %s, status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE file_id = %s
                    """,
                    (len(records), "bronze_registered", str(file_id)),
                )
            conn.commit()
        return len(records)

    def update_file_status(
        self,
        file_id: uuid.UUID,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        if not self.enabled:
            return
        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE bronze_raw.ingested_files
                    SET status = %s, error_message = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE file_id = %s
                    """,
                    (status, error_message, str(file_id)),
                )
            conn.commit()

    def complete_run(
        self,
        run_id: str,
        status: str,
        files_landed: int,
        records_processed: int,
        gold_operational_key: Optional[str],
        gold_analytics_key: Optional[str],
        error_message: Optional[str] = None,
    ) -> None:
        if not self.enabled:
            return
        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE pipeline_audit.pipeline_runs
                    SET status = %s,
                        files_landed = %s,
                        records_processed = %s,
                        gold_operational_key = %s,
                        gold_analytics_key = %s,
                        error_message = %s,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE run_id = %s
                    """,
                    (
                        status,
                        files_landed,
                        records_processed,
                        gold_operational_key,
                        gold_analytics_key,
                        error_message,
                        run_id,
                    ),
                )
            conn.commit()
