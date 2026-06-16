from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import psycopg2
from psycopg2.extras import Json, execute_values

from config.settings import PostgresSettings


LOGGER = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


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
            "CREATE SCHEMA IF NOT EXISTS metadata_catalog",
            "CREATE SCHEMA IF NOT EXISTS iceberg_catalog",
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
            """
            CREATE TABLE IF NOT EXISTS metadata_catalog.object_store_objects (
                object_key TEXT PRIMARY KEY,
                run_id TEXT,
                bucket TEXT NOT NULL,
                object_uri TEXT NOT NULL,
                layer TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                content_type TEXT,
                size_bytes BIGINT,
                checksum_sha256 TEXT,
                source_filename TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS metadata_catalog.gold_artifacts (
                run_id TEXT NOT NULL,
                artifact_name TEXT NOT NULL,
                object_key TEXT NOT NULL,
                record_count INTEGER NOT NULL DEFAULT 0,
                schema_version TEXT,
                data_product_version TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (run_id, artifact_name)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS iceberg_catalog.catalog_bootstrap (
                catalog_name TEXT PRIMARY KEY,
                warehouse_uri TEXT NOT NULL,
                namespace TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "ALTER TABLE pipeline_audit.pipeline_runs ADD COLUMN IF NOT EXISTS pipeline_version TEXT",
            "ALTER TABLE pipeline_audit.pipeline_runs ADD COLUMN IF NOT EXISTS data_product_version TEXT",
            "ALTER TABLE metadata_catalog.gold_artifacts ADD COLUMN IF NOT EXISTS schema_version TEXT",
            "ALTER TABLE metadata_catalog.gold_artifacts ADD COLUMN IF NOT EXISTS data_product_version TEXT",
        ]

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
            conn.commit()

    def healthcheck(self, initialise: bool = True) -> Dict[str, Any]:
        """
        Validate that Postgres is reachable and has the schemas/tables expected
        by the current MinIO medallion pipeline.
        """
        expected_tables = {
            "bronze_raw": ["ingested_files", "ingested_records"],
            "pipeline_audit": ["pipeline_runs"],
            "metadata_catalog": ["object_store_objects", "gold_artifacts"],
            "iceberg_catalog": ["catalog_bootstrap"],
        }
        expected_columns = {
            ("bronze_raw", "ingested_files"): [
                "file_id",
                "run_id",
                "bucket",
                "object_key",
                "object_uri",
                "original_filename",
                "file_extension",
                "status",
                "record_count",
            ],
            ("bronze_raw", "ingested_records"): [
                "record_id",
                "file_id",
                "run_id",
                "record_ordinal",
                "raw_payload",
            ],
            ("pipeline_audit", "pipeline_runs"): [
                "run_id",
                "status",
                "pipeline_version",
                "data_product_version",
                "records_processed",
                "gold_operational_key",
                "gold_analytics_key",
            ],
            ("metadata_catalog", "object_store_objects"): [
                "object_key",
                "run_id",
                "bucket",
                "object_uri",
                "layer",
                "artifact_type",
                "checksum_sha256",
            ],
            ("metadata_catalog", "gold_artifacts"): [
                "run_id",
                "artifact_name",
                "object_key",
                "record_count",
                "schema_version",
                "data_product_version",
            ],
            ("iceberg_catalog", "catalog_bootstrap"): [
                "catalog_name",
                "warehouse_uri",
                "namespace",
                "status",
            ],
        }

        if not self.enabled:
            return {
                "enabled": False,
                "reachable": False,
                "valid": False,
                "missing_tables": [],
                "missing_columns": {},
                "message": "Postgres settings are not configured.",
            }

        missing_tables = []
        missing_columns: Dict[str, list[str]] = {}

        try:
            if initialise:
                self.initialise()

            with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET statement_timeout = '5s'")
                    cur.execute("SELECT 1")
                    for schema, tables in expected_tables.items():
                        for table in tables:
                            cur.execute(
                                """
                                SELECT EXISTS (
                                    SELECT 1
                                    FROM information_schema.tables
                                    WHERE table_schema = %s AND table_name = %s
                                )
                                """,
                                (schema, table),
                            )
                            exists = bool(cur.fetchone()[0])
                            if not exists:
                                missing_tables.append(f"{schema}.{table}")
                                continue

                            cur.execute(
                                """
                                SELECT column_name
                                FROM information_schema.columns
                                WHERE table_schema = %s AND table_name = %s
                                """,
                                (schema, table),
                            )
                            actual_columns = {row[0] for row in cur.fetchall()}
                            required_columns = expected_columns.get((schema, table), [])
                            missing = [
                                column for column in required_columns if column not in actual_columns
                            ]
                            if missing:
                                missing_columns[f"{schema}.{table}"] = missing
        except psycopg2.Error as exc:
            return {
                "enabled": True,
                "reachable": False,
                "valid": False,
                "missing_tables": [],
                "missing_columns": {},
                "message": str(exc).strip(),
            }

        return {
            "enabled": True,
            "reachable": True,
            "valid": not missing_tables and not missing_columns,
            "missing_tables": missing_tables,
            "missing_columns": missing_columns,
            "message": "Postgres metadata catalogue is aligned with the pipeline.",
        }

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
            self.record_iceberg_status(
                catalog_name="surgeon_preference",
                warehouse_uri=warehouse_uri,
                namespace="bronze_raw",
                status="available",
            )
        except Exception:
            LOGGER.exception("Iceberg catalog bootstrap failed; Postgres bronze ledger remains available.")
            self.record_iceberg_status(
                catalog_name="surgeon_preference",
                warehouse_uri=warehouse_uri,
                namespace="bronze_raw",
                status="bootstrap_failed",
                error_message="See pipeline logs for pyiceberg exception details.",
            )

    def record_iceberg_status(
        self,
        catalog_name: str,
        warehouse_uri: str,
        namespace: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        if not self.enabled:
            return
        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO iceberg_catalog.catalog_bootstrap (
                        catalog_name, warehouse_uri, namespace, status, error_message
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (catalog_name)
                    DO UPDATE SET warehouse_uri = EXCLUDED.warehouse_uri,
                                  namespace = EXCLUDED.namespace,
                                  status = EXCLUDED.status,
                                  error_message = EXCLUDED.error_message,
                                  updated_at = CURRENT_TIMESTAMP
                    """,
                    (catalog_name, warehouse_uri, namespace, status, error_message),
                )
            conn.commit()

    def register_object(self, metadata: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO metadata_catalog.object_store_objects (
                        object_key, run_id, bucket, object_uri, layer, artifact_type,
                        content_type, size_bytes, checksum_sha256, source_filename
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (object_key)
                    DO UPDATE SET run_id = EXCLUDED.run_id,
                                  bucket = EXCLUDED.bucket,
                                  object_uri = EXCLUDED.object_uri,
                                  layer = EXCLUDED.layer,
                                  artifact_type = EXCLUDED.artifact_type,
                                  content_type = EXCLUDED.content_type,
                                  size_bytes = EXCLUDED.size_bytes,
                                  checksum_sha256 = EXCLUDED.checksum_sha256,
                                  source_filename = EXCLUDED.source_filename
                    """,
                    (
                        metadata["object_key"],
                        metadata.get("run_id"),
                        metadata["bucket"],
                        metadata["object_uri"],
                        metadata["layer"],
                        metadata["artifact_type"],
                        metadata.get("content_type"),
                        metadata.get("size_bytes"),
                        metadata.get("checksum_sha256"),
                        metadata.get("source_filename"),
                    ),
                )
            conn.commit()

    def register_gold_artifacts(
        self,
        run_id: str,
        artifacts: Dict[str, str],
        record_count: int,
        schema_version: Optional[str] = None,
        data_product_version: Optional[str] = None,
    ) -> None:
        if not self.enabled:
            return
        values = [
            (run_id, artifact_name, object_key, record_count, schema_version, data_product_version)
            for artifact_name, object_key in artifacts.items()
        ]
        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    INSERT INTO metadata_catalog.gold_artifacts (
                        run_id, artifact_name, object_key, record_count,
                        schema_version, data_product_version
                    )
                    VALUES %s
                    ON CONFLICT (run_id, artifact_name)
                    DO UPDATE SET object_key = EXCLUDED.object_key,
                                  record_count = EXCLUDED.record_count,
                                  schema_version = EXCLUDED.schema_version,
                                  data_product_version = EXCLUDED.data_product_version,
                                  created_at = CURRENT_TIMESTAMP
                    """,
                    values,
                )
            conn.commit()

    def start_run(
        self,
        run_id: str,
        source_path: str,
        pipeline_version: Optional[str] = None,
        data_product_version: Optional[str] = None,
    ) -> None:
        if not self.enabled:
            return
        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pipeline_audit.pipeline_runs (
                        run_id, status, source_path, pipeline_version, data_product_version
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (run_id)
                    DO UPDATE SET status = EXCLUDED.status,
                                  source_path = EXCLUDED.source_path,
                                  pipeline_version = EXCLUDED.pipeline_version,
                                  data_product_version = EXCLUDED.data_product_version
                    """,
                    (run_id, "running", source_path, pipeline_version, data_product_version),
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
            (str(uuid.uuid4()), str(file_id), run_id, idx, Json(_json_safe(record)))
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
