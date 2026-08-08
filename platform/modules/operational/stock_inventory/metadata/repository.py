from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config.settings import PipelineSettings, PostgresSettings


MIGRATION_PATH = Path(__file__).parent / "migrations" / "001_initial_metadata.sql"


class PostgresMetadataRepository:
    def __init__(self, settings: PostgresSettings):
        self.settings = settings

    def _connect(self):
        try:
            import psycopg2
        except ImportError as exc:
            raise ImportError("psycopg2-binary is required for PostgreSQL metadata support") from exc
        return psycopg2.connect(
            host=self.settings.host,
            port=self.settings.port,
            dbname=self.settings.database,
            user=self.settings.user,
            password=self.settings.password,
            sslmode=self.settings.sslmode,
            connect_timeout=5,
        )

    def migrate(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(MIGRATION_PATH.read_text(encoding="utf-8"))

    def grant_runtime_access(self, runtime_user: str) -> None:
        from psycopg2 import sql

        role = sql.Identifier(runtime_user)
        statements = (
            sql.SQL("GRANT USAGE ON SCHEMA stock_metadata TO {}").format(role),
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA stock_metadata TO {}"
            ).format(role),
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA stock_metadata "
                "GRANT SELECT, INSERT, UPDATE ON TABLES TO {}"
            ).format(role),
        )
        with self._connect() as connection, connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)

    def start_run(self, run_id: str, source_dir: str) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO stock_metadata.pipeline_runs (run_id, source_dir, status)
                VALUES (%s, %s, 'running')
                """,
                (run_id, source_dir),
            )

    def record_stage(self, run_id: str, stage: str, manifest_path: str, record_count: int) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO stock_metadata.pipeline_stages
                    (run_id, stage_name, status, record_count, manifest_path)
                VALUES (%s, %s, 'completed', %s, %s)
                ON CONFLICT (run_id, stage_name) DO UPDATE SET
                    status = 'completed', record_count = EXCLUDED.record_count,
                    manifest_path = EXCLUDED.manifest_path, completed_at = now()
                """,
                (run_id, stage, record_count, manifest_path),
            )

    def record_ingested_files(self, run_id: str, bronze_manifest_path: str) -> None:
        manifest = json.loads(Path(bronze_manifest_path).read_text(encoding="utf-8"))
        rows = manifest.get("source_files", [])
        if not rows:
            return
        with self._connect() as connection, connection.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    """
                    INSERT INTO stock_metadata.ingested_files
                        (source_file_id, run_id, dataset_name, source_path, raw_path, file_name,
                         file_extension, size_bytes, checksum_sha256, canonical_for_silver, ingested_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_file_id) DO NOTHING
                    """,
                    (
                        row["source_file_id"], run_id, row["dataset"], row["source_path"],
                        row["raw_path"], row["file_name"], row["file_extension"], row["size_bytes"],
                        row["checksum_sha256"], row["canonical_for_silver"], row["ingested_at"],
                    ),
                )

    def complete_run(self, run_id: str, pipeline_manifest_path: str) -> None:
        self._finish_run(run_id, "completed", pipeline_manifest_path, None)

    def fail_run(self, run_id: str, error_message: str) -> None:
        self._finish_run(run_id, "failed", None, error_message[:4000])

    def _finish_run(
        self, run_id: str, status: str, pipeline_manifest_path: str | None, error_message: str | None
    ) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE stock_metadata.pipeline_runs
                SET status = %s, completed_at = now(), pipeline_manifest_path = COALESCE(%s, pipeline_manifest_path),
                    error_message = %s, updated_at = now()
                WHERE run_id = %s
                """,
                (status, pipeline_manifest_path, error_message, run_id),
            )

    def record_quality_result(self, result: Any) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            for check in result.checks:
                cursor.execute(
                    """
                    INSERT INTO stock_metadata.quality_gate_results
                        (run_id, check_name, passed, severity, message, metadata, checked_at)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (run_id, check_name) DO UPDATE SET
                        passed = EXCLUDED.passed, severity = EXCLUDED.severity,
                        message = EXCLUDED.message, metadata = EXCLUDED.metadata,
                        checked_at = EXCLUDED.checked_at
                    """,
                    (
                        result.run_id, check["name"], check["passed"], check["severity"],
                        check["message"], json.dumps(check.get("metadata", {})), result.checked_at,
                    ),
                )

    def record_published_artifacts(self, result: Any) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            for artifact in result.artifacts:
                cursor.execute(
                    """
                    INSERT INTO stock_metadata.published_artifacts
                        (run_id, object_key, object_uri, local_path, content_type, checksum_sha256, published_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_id, object_key) DO UPDATE SET
                        object_uri = EXCLUDED.object_uri, local_path = EXCLUDED.local_path,
                        content_type = EXCLUDED.content_type, checksum_sha256 = EXCLUDED.checksum_sha256,
                        published_at = EXCLUDED.published_at
                    """,
                    (
                        result.run_id, artifact["object_key"], artifact["object_uri"], artifact["local_path"],
                        artifact["content_type"], artifact["checksum_sha256"], result.published_at,
                    ),
                )


def metadata_repository_from_settings(settings: PipelineSettings) -> PostgresMetadataRepository | None:
    if settings.postgres is None:
        return None
    return PostgresMetadataRepository(settings.postgres)
