from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import psycopg2
from psycopg2.extras import Json, RealDictCursor, execute_values

from config.settings import PostgresSettings


LOGGER = logging.getLogger(__name__)
APP_USER_STATUSES = {"pending_access", "active", "suspended"}
APP_USER_ROLES = {"authenticated", "editor", "reviewer", "admin"}
ACCESS_REQUEST_STATUSES = {"pending_review", "approved", "rejected"}
DEFAULT_ORGANISATION_ID = "default"
DEFAULT_ORGANISATION_NAME = "Surgeon Preference Demo"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _safe_organisation_id(value: Any) -> str:
    organisation_id = str(value or "").strip().lower().replace(" ", "-")
    return organisation_id or DEFAULT_ORGANISATION_ID


def _safe_organisation_name(value: Any) -> str:
    organisation_name = str(value or "").strip()
    return organisation_name or DEFAULT_ORGANISATION_NAME


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
            "CREATE SCHEMA IF NOT EXISTS app_workflow",
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
            """
            CREATE TABLE IF NOT EXISTS app_workflow.organisations (
                organisation_id TEXT PRIMARY KEY,
                organisation_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS app_workflow.app_users (
                user_email TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                roles TEXT[] NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending_access',
                default_organisation_id TEXT REFERENCES app_workflow.organisations(organisation_id),
                auth_provider TEXT,
                last_seen_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS app_workflow.organisation_memberships (
                organisation_id TEXT NOT NULL REFERENCES app_workflow.organisations(organisation_id),
                user_email TEXT NOT NULL REFERENCES app_workflow.app_users(user_email),
                roles TEXT[] NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending_access',
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (organisation_id, user_email)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS app_workflow.access_requests (
                access_request_id UUID PRIMARY KEY,
                organisation_id TEXT REFERENCES app_workflow.organisations(organisation_id),
                user_email TEXT NOT NULL REFERENCES app_workflow.app_users(user_email),
                display_name TEXT NOT NULL,
                requested_roles TEXT[] NOT NULL DEFAULT '{}',
                requested_organisation_name TEXT,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'pending_review',
                reviewed_by_email TEXT,
                reviewed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS app_workflow.draft_reviews (
                review_id UUID PRIMARY KEY,
                organisation_id TEXT REFERENCES app_workflow.organisations(organisation_id),
                draft_id TEXT,
                draft_object_key TEXT,
                blob_review_key TEXT,
                draft_type TEXT,
                decision TEXT NOT NULL,
                reviewer_name TEXT NOT NULL,
                reviewer_email TEXT,
                reviewer_roles TEXT[] NOT NULL DEFAULT '{}',
                comments TEXT,
                reviewed_at TIMESTAMPTZ NOT NULL,
                source_gold_key TEXT,
                surgeon_id TEXT,
                surgeon_name TEXT,
                procedure TEXT,
                procedure_id TEXT,
                review_payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS app_workflow.audit_events (
                event_id UUID PRIMARY KEY,
                event_type TEXT NOT NULL,
                organisation_id TEXT REFERENCES app_workflow.organisations(organisation_id),
                actor_email TEXT,
                actor_name TEXT,
                actor_roles TEXT[] NOT NULL DEFAULT '{}',
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                event_payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "ALTER TABLE pipeline_audit.pipeline_runs ADD COLUMN IF NOT EXISTS pipeline_version TEXT",
            "ALTER TABLE pipeline_audit.pipeline_runs ADD COLUMN IF NOT EXISTS data_product_version TEXT",
            "ALTER TABLE metadata_catalog.gold_artifacts ADD COLUMN IF NOT EXISTS schema_version TEXT",
            "ALTER TABLE metadata_catalog.gold_artifacts ADD COLUMN IF NOT EXISTS data_product_version TEXT",
            """
            INSERT INTO app_workflow.organisations (organisation_id, organisation_name, status)
            VALUES ('default', 'Surgeon Preference Demo', 'active')
            ON CONFLICT (organisation_id)
            DO NOTHING
            """,
            (
                "ALTER TABLE app_workflow.app_users ADD COLUMN IF NOT EXISTS "
                "default_organisation_id TEXT REFERENCES app_workflow.organisations(organisation_id)"
            ),
            "ALTER TABLE app_workflow.app_users ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending_access'",
            "ALTER TABLE app_workflow.app_users ADD COLUMN IF NOT EXISTS auth_provider TEXT",
            "ALTER TABLE app_workflow.app_users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ",
            (
                "ALTER TABLE app_workflow.access_requests ADD COLUMN IF NOT EXISTS "
                "organisation_id TEXT REFERENCES app_workflow.organisations(organisation_id)"
            ),
            "ALTER TABLE app_workflow.access_requests ADD COLUMN IF NOT EXISTS requested_organisation_name TEXT",
            "ALTER TABLE app_workflow.access_requests ADD COLUMN IF NOT EXISTS reviewed_by_email TEXT",
            "ALTER TABLE app_workflow.access_requests ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ",
            (
                "ALTER TABLE app_workflow.draft_reviews ADD COLUMN IF NOT EXISTS "
                "organisation_id TEXT REFERENCES app_workflow.organisations(organisation_id)"
            ),
            "ALTER TABLE app_workflow.draft_reviews ADD COLUMN IF NOT EXISTS blob_review_key TEXT",
            (
                "ALTER TABLE app_workflow.audit_events ADD COLUMN IF NOT EXISTS "
                "organisation_id TEXT REFERENCES app_workflow.organisations(organisation_id)"
            ),
            (
                "UPDATE app_workflow.app_users "
                "SET default_organisation_id = 'default' "
                "WHERE default_organisation_id IS NULL"
            ),
            (
                "UPDATE app_workflow.draft_reviews "
                "SET organisation_id = 'default' "
                "WHERE organisation_id IS NULL"
            ),
            (
                "UPDATE app_workflow.audit_events "
                "SET organisation_id = 'default' "
                "WHERE organisation_id IS NULL"
            ),
            """
            INSERT INTO app_workflow.organisation_memberships (
                organisation_id,
                user_email,
                roles,
                status
            )
            SELECT
                COALESCE(default_organisation_id, 'default'),
                user_email,
                roles,
                status
            FROM app_workflow.app_users
            ON CONFLICT (organisation_id, user_email)
            DO NOTHING
            """,
            "CREATE INDEX IF NOT EXISTS idx_organisations_status ON app_workflow.organisations(status)",
            "CREATE INDEX IF NOT EXISTS idx_memberships_user ON app_workflow.organisation_memberships(user_email)",
            "CREATE INDEX IF NOT EXISTS idx_memberships_status ON app_workflow.organisation_memberships(status)",
            "CREATE INDEX IF NOT EXISTS idx_access_requests_org ON app_workflow.access_requests(organisation_id)",
            "CREATE INDEX IF NOT EXISTS idx_access_requests_user ON app_workflow.access_requests(user_email)",
            "CREATE INDEX IF NOT EXISTS idx_access_requests_status ON app_workflow.access_requests(status)",
            "CREATE INDEX IF NOT EXISTS idx_app_users_status ON app_workflow.app_users(status)",
            "CREATE INDEX IF NOT EXISTS idx_app_users_default_org ON app_workflow.app_users(default_organisation_id)",
            "CREATE INDEX IF NOT EXISTS idx_draft_reviews_org ON app_workflow.draft_reviews(organisation_id)",
            "CREATE INDEX IF NOT EXISTS idx_draft_reviews_draft_id ON app_workflow.draft_reviews(draft_id)",
            "CREATE INDEX IF NOT EXISTS idx_draft_reviews_decision ON app_workflow.draft_reviews(decision)",
            "CREATE INDEX IF NOT EXISTS idx_audit_events_org ON app_workflow.audit_events(organisation_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_events_entity ON app_workflow.audit_events(entity_type, entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_events_actor ON app_workflow.audit_events(actor_email)",
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
            "app_workflow": [
                "organisations",
                "app_users",
                "organisation_memberships",
                "access_requests",
                "draft_reviews",
                "audit_events",
            ],
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
            ("app_workflow", "app_users"): [
                "user_email",
                "display_name",
                "roles",
                "status",
                "default_organisation_id",
                "auth_provider",
                "last_seen_at",
                "created_at",
                "updated_at",
            ],
            ("app_workflow", "organisations"): [
                "organisation_id",
                "organisation_name",
                "status",
                "created_at",
                "updated_at",
            ],
            ("app_workflow", "organisation_memberships"): [
                "organisation_id",
                "user_email",
                "roles",
                "status",
                "created_at",
                "updated_at",
            ],
            ("app_workflow", "access_requests"): [
                "access_request_id",
                "organisation_id",
                "user_email",
                "display_name",
                "requested_roles",
                "requested_organisation_name",
                "reason",
                "status",
                "reviewed_by_email",
                "reviewed_at",
                "created_at",
                "updated_at",
            ],
            ("app_workflow", "draft_reviews"): [
                "review_id",
                "organisation_id",
                "draft_id",
                "draft_object_key",
                "blob_review_key",
                "draft_type",
                "decision",
                "reviewer_name",
                "reviewer_email",
                "reviewer_roles",
                "comments",
                "reviewed_at",
                "review_payload",
            ],
            ("app_workflow", "audit_events"): [
                "event_id",
                "event_type",
                "organisation_id",
                "actor_email",
                "actor_name",
                "actor_roles",
                "entity_type",
                "entity_id",
                "event_payload",
                "created_at",
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

    @staticmethod
    def _upsert_organisation_and_membership(
        cur,
        organisation_id: str,
        organisation_name: str,
        user_email: str,
        roles: list[str],
        status: str,
    ) -> None:
        cur.execute(
            """
            INSERT INTO app_workflow.organisations (
                organisation_id,
                organisation_name,
                status
            )
            VALUES (%s, %s, 'active')
            ON CONFLICT (organisation_id)
            DO UPDATE SET organisation_name = EXCLUDED.organisation_name,
                          updated_at = CURRENT_TIMESTAMP
            """,
            (organisation_id, organisation_name),
        )
        cur.execute(
            """
            INSERT INTO app_workflow.organisation_memberships (
                organisation_id,
                user_email,
                roles,
                status
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (organisation_id, user_email)
            DO UPDATE SET roles = EXCLUDED.roles,
                          status = EXCLUDED.status,
                          updated_at = CURRENT_TIMESTAMP
            """,
            (organisation_id, user_email, roles, status),
        )

    def upsert_app_user_seen(
        self,
        user_email: str,
        display_name: str,
        roles: list[str],
        status: str,
        auth_provider: str,
        organisation_id: str = DEFAULT_ORGANISATION_ID,
        organisation_name: str = DEFAULT_ORGANISATION_NAME,
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        normalised_email = user_email.strip().lower()
        safe_roles = sorted({role.strip().lower() for role in roles if role.strip()})
        safe_organisation_id = _safe_organisation_id(organisation_id)
        safe_organisation_name = _safe_organisation_name(organisation_name)
        if not normalised_email:
            raise ValueError("User email is required.")

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO app_workflow.organisations (
                        organisation_id,
                        organisation_name,
                        status
                    )
                    VALUES (%s, %s, 'active')
                    ON CONFLICT (organisation_id)
                    DO UPDATE SET organisation_name = EXCLUDED.organisation_name,
                                  updated_at = CURRENT_TIMESTAMP
                    """,
                    (safe_organisation_id, safe_organisation_name),
                )
                cur.execute(
                    """
                    INSERT INTO app_workflow.app_users (
                        user_email,
                        display_name,
                        roles,
                        status,
                        default_organisation_id,
                        auth_provider,
                        last_seen_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_email)
                    DO UPDATE SET display_name = EXCLUDED.display_name,
                                  roles = CASE
                                      WHEN app_workflow.app_users.status = 'pending_access'
                                           AND EXCLUDED.status = 'active'
                                      THEN EXCLUDED.roles
                                      ELSE app_workflow.app_users.roles
                                  END,
                                  status = CASE
                                      WHEN app_workflow.app_users.status = 'pending_access'
                                           AND EXCLUDED.status = 'active'
                                      THEN 'active'
                                      ELSE app_workflow.app_users.status
                                  END,
                                  default_organisation_id = EXCLUDED.default_organisation_id,
                                  auth_provider = EXCLUDED.auth_provider,
                                  last_seen_at = CURRENT_TIMESTAMP,
                                  updated_at = CURRENT_TIMESTAMP
                    RETURNING
                        user_email,
                        display_name,
                        roles,
                        status,
                        default_organisation_id AS organisation_id,
                        %s AS organisation_name,
                        auth_provider,
                        created_at,
                        updated_at,
                        last_seen_at
                    """,
                    (
                        normalised_email,
                        display_name.strip() or normalised_email,
                        safe_roles,
                        status,
                        safe_organisation_id,
                        auth_provider,
                        safe_organisation_name,
                    ),
                )
                row = cur.fetchone()
                self._upsert_organisation_and_membership(
                    cur,
                    safe_organisation_id,
                    safe_organisation_name,
                    normalised_email,
                    safe_roles,
                    status,
                )
            conn.commit()

        return dict(row) if row else None

    def list_app_users(self, limit: int = 100) -> list[Dict[str, Any]]:
        if not self.enabled:
            return []

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        users.user_email,
                        users.display_name,
                        users.roles,
                        users.status,
                        users.default_organisation_id AS organisation_id,
                        organisations.organisation_name,
                        users.auth_provider,
                        users.created_at,
                        users.updated_at,
                        users.last_seen_at
                    FROM app_workflow.app_users users
                    LEFT JOIN app_workflow.organisations organisations
                        ON users.default_organisation_id = organisations.organisation_id
                    ORDER BY users.updated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()

        return [dict(row) for row in rows]

    def create_access_request(
        self,
        user_email: str,
        display_name: str,
        requested_roles: list[str],
        requested_organisation_name: str,
        reason: str,
        organisation_id: str = DEFAULT_ORGANISATION_ID,
        organisation_name: str = DEFAULT_ORGANISATION_NAME,
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        normalised_email = user_email.strip().lower()
        safe_roles = sorted({role.strip().lower() for role in requested_roles if role.strip()})
        safe_organisation_id = _safe_organisation_id(organisation_id)
        safe_organisation_name = _safe_organisation_name(organisation_name)
        requested_organisation_name = requested_organisation_name.strip() or safe_organisation_name
        reason = reason.strip()

        if not normalised_email:
            raise ValueError("User email is required.")
        if "@" not in normalised_email:
            raise ValueError("User email must look like an email address.")
        invalid_roles = sorted(set(safe_roles) - APP_USER_ROLES)
        if invalid_roles:
            raise ValueError(f"Invalid requested roles: {', '.join(invalid_roles)}")
        if "authenticated" not in safe_roles:
            safe_roles = ["authenticated", *safe_roles]
        if not reason:
            raise ValueError("Access request reason is required.")

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO app_workflow.organisations (
                        organisation_id,
                        organisation_name,
                        status
                    )
                    VALUES (%s, %s, 'active')
                    ON CONFLICT (organisation_id)
                    DO UPDATE SET organisation_name = EXCLUDED.organisation_name,
                                  updated_at = CURRENT_TIMESTAMP
                    """,
                    (safe_organisation_id, safe_organisation_name),
                )
                cur.execute(
                    """
                    INSERT INTO app_workflow.app_users (
                        user_email,
                        display_name,
                        roles,
                        status,
                        default_organisation_id,
                        auth_provider,
                        last_seen_at
                    )
                    VALUES (%s, %s, ARRAY['authenticated'], 'pending_access', %s, 'access_request', CURRENT_TIMESTAMP)
                    ON CONFLICT (user_email)
                    DO UPDATE SET display_name = EXCLUDED.display_name,
                                  default_organisation_id = EXCLUDED.default_organisation_id,
                                  last_seen_at = CURRENT_TIMESTAMP,
                                  updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        normalised_email,
                        display_name.strip() or normalised_email,
                        safe_organisation_id,
                    ),
                )
                self._upsert_organisation_and_membership(
                    cur,
                    safe_organisation_id,
                    safe_organisation_name,
                    normalised_email,
                    ["authenticated"],
                    "pending_access",
                )
                cur.execute(
                    """
                    UPDATE app_workflow.access_requests
                    SET display_name = %s,
                        requested_roles = %s,
                        requested_organisation_name = %s,
                        reason = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE organisation_id = %s
                      AND user_email = %s
                      AND status = 'pending_review'
                    RETURNING
                        access_request_id,
                        organisation_id,
                        user_email,
                        display_name,
                        requested_roles,
                        requested_organisation_name,
                        reason,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        display_name.strip() or normalised_email,
                        safe_roles,
                        requested_organisation_name,
                        reason,
                        safe_organisation_id,
                        normalised_email,
                    ),
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        """
                        INSERT INTO app_workflow.access_requests (
                            access_request_id,
                            organisation_id,
                            user_email,
                            display_name,
                            requested_roles,
                            requested_organisation_name,
                            reason,
                            status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending_review')
                        RETURNING
                            access_request_id,
                            organisation_id,
                            user_email,
                            display_name,
                            requested_roles,
                            requested_organisation_name,
                            reason,
                            status,
                            created_at,
                            updated_at
                        """,
                        (
                            str(uuid.uuid4()),
                            safe_organisation_id,
                            normalised_email,
                            display_name.strip() or normalised_email,
                            safe_roles,
                            requested_organisation_name,
                            reason,
                        ),
                    )
                    row = cur.fetchone()
                cur.execute(
                    """
                    INSERT INTO app_workflow.audit_events (
                        event_id,
                        event_type,
                        organisation_id,
                        actor_email,
                        actor_name,
                        actor_roles,
                        entity_type,
                        entity_id,
                        event_payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        "app_access_requested",
                        safe_organisation_id,
                        normalised_email,
                        display_name.strip() or normalised_email,
                        ["authenticated"],
                        "access_request",
                        str(row["access_request_id"]) if row else None,
                        Json(
                            _json_safe(
                                {
                                    "user_email": normalised_email,
                                    "display_name": display_name.strip() or normalised_email,
                                    "requested_roles": safe_roles,
                                    "requested_organisation_name": requested_organisation_name,
                                    "reason": reason,
                                    "organisation_id": safe_organisation_id,
                                    "organisation_name": safe_organisation_name,
                                }
                            )
                        ),
                    ),
                )
            conn.commit()

        return dict(row) if row else None

    def list_access_requests(
        self,
        organisation_id: str | None = None,
        status: str | None = None,
        user_email: str | None = None,
        limit: int = 100,
    ) -> list[Dict[str, Any]]:
        if not self.enabled:
            return []

        filters = []
        params: list[Any] = []
        if organisation_id:
            filters.append("requests.organisation_id = %s")
            params.append(_safe_organisation_id(organisation_id))
        if status:
            filters.append("requests.status = %s")
            params.append(status.strip().lower())
        if user_email:
            filters.append("requests.user_email = %s")
            params.append(user_email.strip().lower())
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT
                        requests.access_request_id,
                        requests.organisation_id,
                        organisations.organisation_name,
                        requests.user_email,
                        requests.display_name,
                        requests.requested_roles,
                        requests.requested_organisation_name,
                        requests.reason,
                        requests.status,
                        requests.reviewed_by_email,
                        requests.reviewed_at,
                        requests.created_at,
                        requests.updated_at
                    FROM app_workflow.access_requests requests
                    LEFT JOIN app_workflow.organisations organisations
                        ON requests.organisation_id = organisations.organisation_id
                    {where_clause}
                    ORDER BY requests.created_at DESC
                    LIMIT %s
                    """,
                    params,
                )
                rows = cur.fetchall()

        return [dict(row) for row in rows]

    def resolve_access_request(
        self,
        access_request_id: str,
        decision: str,
        actor_email: str,
        actor_name: str,
        actor_roles: list[str],
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        normalised_decision = decision.strip().lower()
        if normalised_decision not in {"approved", "rejected"}:
            raise ValueError("Access request decision must be approved or rejected.")

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        access_request_id,
                        organisation_id,
                        user_email,
                        display_name,
                        requested_roles,
                        requested_organisation_name,
                        reason,
                        status
                    FROM app_workflow.access_requests
                    WHERE access_request_id = %s
                    FOR UPDATE
                    """,
                    (access_request_id,),
                )
                request_row = cur.fetchone()
                if not request_row:
                    raise ValueError("Access request was not found.")

                if normalised_decision == "approved":
                    approved_roles = sorted(
                        {
                            str(role).strip().lower()
                            for role in request_row["requested_roles"] or []
                            if str(role).strip()
                        }
                    )
                    if "authenticated" not in approved_roles:
                        approved_roles = ["authenticated", *approved_roles]
                    safe_organisation_id = _safe_organisation_id(request_row["organisation_id"])
                    safe_organisation_name = _safe_organisation_name(
                        request_row.get("requested_organisation_name")
                    )
                    cur.execute(
                        """
                        INSERT INTO app_workflow.app_users (
                            user_email,
                            display_name,
                            roles,
                            status,
                            default_organisation_id,
                            auth_provider
                        )
                        VALUES (%s, %s, %s, 'active', %s, 'access_request')
                        ON CONFLICT (user_email)
                        DO UPDATE SET display_name = EXCLUDED.display_name,
                                      roles = EXCLUDED.roles,
                                      status = EXCLUDED.status,
                                      default_organisation_id = EXCLUDED.default_organisation_id,
                                      auth_provider = EXCLUDED.auth_provider,
                                      updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            request_row["user_email"],
                            request_row["display_name"],
                            approved_roles,
                            safe_organisation_id,
                        ),
                    )
                    self._upsert_organisation_and_membership(
                        cur,
                        safe_organisation_id,
                        safe_organisation_name,
                        request_row["user_email"],
                        approved_roles,
                        "active",
                    )
                    cur.execute(
                        """
                        INSERT INTO app_workflow.audit_events (
                            event_id,
                            event_type,
                            organisation_id,
                            actor_email,
                            actor_name,
                            actor_roles,
                            entity_type,
                            entity_id,
                            event_payload
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(uuid.uuid4()),
                            "app_user_access_updated",
                            safe_organisation_id,
                            actor_email.strip().lower(),
                            actor_name.strip() or actor_email.strip().lower(),
                            actor_roles,
                            "app_user",
                            request_row["user_email"],
                            Json(
                                _json_safe(
                                    {
                                        "user_email": request_row["user_email"],
                                        "display_name": request_row["display_name"],
                                        "roles": approved_roles,
                                        "status": "active",
                                        "actor_email": actor_email.strip().lower(),
                                        "actor_name": actor_name.strip() or actor_email.strip().lower(),
                                        "actor_roles": actor_roles,
                                        "organisation_id": safe_organisation_id,
                                        "organisation_name": safe_organisation_name,
                                        "access_request_id": str(access_request_id),
                                    }
                                )
                            ),
                        ),
                    )

                cur.execute(
                    """
                    UPDATE app_workflow.access_requests
                    SET status = %s,
                        reviewed_by_email = %s,
                        reviewed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE access_request_id = %s
                    RETURNING
                        access_request_id,
                        organisation_id,
                        user_email,
                        display_name,
                        requested_roles,
                        requested_organisation_name,
                        reason,
                        status,
                        reviewed_by_email,
                        reviewed_at,
                        created_at,
                        updated_at
                    """,
                    (normalised_decision, actor_email.strip().lower(), access_request_id),
                )
                resolved_row = cur.fetchone()
                cur.execute(
                    """
                    INSERT INTO app_workflow.audit_events (
                        event_id,
                        event_type,
                        organisation_id,
                        actor_email,
                        actor_name,
                        actor_roles,
                        entity_type,
                        entity_id,
                        event_payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        "app_access_request_resolved",
                        request_row["organisation_id"],
                        actor_email.strip().lower(),
                        actor_name.strip() or actor_email.strip().lower(),
                        actor_roles,
                        "access_request",
                        str(access_request_id),
                        Json(
                            _json_safe(
                                {
                                    **dict(request_row),
                                    "decision": normalised_decision,
                                    "actor_email": actor_email.strip().lower(),
                                    "actor_name": actor_name.strip() or actor_email.strip().lower(),
                                    "actor_roles": actor_roles,
                                }
                            )
                        ),
                    ),
                )
            conn.commit()

        return dict(resolved_row) if resolved_row else None

    def update_app_user_access(
        self,
        user_email: str,
        display_name: str,
        roles: list[str],
        status: str,
        actor_email: str,
        actor_name: str,
        actor_roles: list[str],
        organisation_id: str = DEFAULT_ORGANISATION_ID,
        organisation_name: str = DEFAULT_ORGANISATION_NAME,
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        normalised_email = user_email.strip().lower()
        normalised_actor_email = actor_email.strip().lower()
        normalised_status = status.strip().lower()
        safe_roles = sorted({role.strip().lower() for role in roles if role.strip()})
        safe_organisation_id = _safe_organisation_id(organisation_id)
        safe_organisation_name = _safe_organisation_name(organisation_name)

        if not normalised_email:
            raise ValueError("User email is required.")
        if "@" not in normalised_email:
            raise ValueError("User email must look like an email address.")
        if normalised_status not in APP_USER_STATUSES:
            raise ValueError(f"Invalid user status: {status}")
        invalid_roles = sorted(set(safe_roles) - APP_USER_ROLES)
        if invalid_roles:
            raise ValueError(f"Invalid app user roles: {', '.join(invalid_roles)}")
        if "authenticated" not in safe_roles:
            safe_roles = ["authenticated", *safe_roles]
        if normalised_email == normalised_actor_email:
            if normalised_status != "active":
                raise ValueError("Administrators cannot suspend or deactivate their own account.")
            if "admin" not in safe_roles:
                raise ValueError("Administrators cannot remove their own admin role.")

        event_payload = {
            "user_email": normalised_email,
            "display_name": display_name.strip() or normalised_email,
            "roles": safe_roles,
            "status": normalised_status,
            "actor_email": normalised_actor_email,
            "actor_name": actor_name.strip() or normalised_actor_email,
            "actor_roles": actor_roles,
            "organisation_id": safe_organisation_id,
            "organisation_name": safe_organisation_name,
        }

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO app_workflow.organisations (
                        organisation_id,
                        organisation_name,
                        status
                    )
                    VALUES (%s, %s, 'active')
                    ON CONFLICT (organisation_id)
                    DO UPDATE SET organisation_name = EXCLUDED.organisation_name,
                                  updated_at = CURRENT_TIMESTAMP
                    """,
                    (safe_organisation_id, safe_organisation_name),
                )
                cur.execute(
                    """
                    INSERT INTO app_workflow.app_users (
                        user_email,
                        display_name,
                        roles,
                        status,
                        default_organisation_id,
                        auth_provider
                    )
                    VALUES (%s, %s, %s, %s, %s, 'manual_admin')
                    ON CONFLICT (user_email)
                    DO UPDATE SET display_name = EXCLUDED.display_name,
                                  roles = EXCLUDED.roles,
                                  status = EXCLUDED.status,
                                  default_organisation_id = EXCLUDED.default_organisation_id,
                                  auth_provider = EXCLUDED.auth_provider,
                                  updated_at = CURRENT_TIMESTAMP
                    RETURNING
                        user_email,
                        display_name,
                        roles,
                        status,
                        default_organisation_id AS organisation_id,
                        %s AS organisation_name,
                        auth_provider,
                        created_at,
                        updated_at,
                        last_seen_at
                    """,
                    (
                        normalised_email,
                        display_name.strip() or normalised_email,
                        safe_roles,
                        normalised_status,
                        safe_organisation_id,
                        safe_organisation_name,
                    ),
                )
                row = cur.fetchone()
                self._upsert_organisation_and_membership(
                    cur,
                    safe_organisation_id,
                    safe_organisation_name,
                    normalised_email,
                    safe_roles,
                    normalised_status,
                )

                cur.execute(
                    """
                    INSERT INTO app_workflow.audit_events (
                        event_id,
                        event_type,
                        organisation_id,
                        actor_email,
                        actor_name,
                        actor_roles,
                        entity_type,
                        entity_id,
                        event_payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        "app_user_access_updated",
                        safe_organisation_id,
                        normalised_actor_email,
                        actor_name.strip() or normalised_actor_email,
                        actor_roles,
                        "app_user",
                        normalised_email,
                        Json(_json_safe(event_payload)),
                    ),
                )
            conn.commit()

        return dict(row) if row else None

    def record_draft_submission(self, draft: Dict[str, Any], draft_object_key: str) -> None:
        if not self.enabled:
            return

        submitter_email = draft.get("submitter_email") or None
        submitter_name = draft.get("submitted_by") or "Unknown submitter"
        submitter_roles = list(draft.get("submitter_roles") or [])
        organisation_id = _safe_organisation_id(draft.get("organisation_id"))
        organisation_name = _safe_organisation_name(draft.get("organisation_name"))
        event_payload = {**draft, "draft_object_key": draft_object_key}

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app_workflow.organisations (
                        organisation_id,
                        organisation_name,
                        status
                    )
                    VALUES (%s, %s, 'active')
                    ON CONFLICT (organisation_id)
                    DO UPDATE SET organisation_name = EXCLUDED.organisation_name,
                                  updated_at = CURRENT_TIMESTAMP
                    """,
                    (organisation_id, organisation_name),
                )
                if submitter_email:
                    cur.execute(
                        """
                        INSERT INTO app_workflow.app_users (
                            user_email,
                            display_name,
                            roles,
                            status,
                            default_organisation_id,
                            auth_provider,
                            last_seen_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (user_email)
                        DO UPDATE SET display_name = EXCLUDED.display_name,
                                      default_organisation_id = EXCLUDED.default_organisation_id,
                                      auth_provider = EXCLUDED.auth_provider,
                                      last_seen_at = CURRENT_TIMESTAMP,
                                      updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            submitter_email,
                            submitter_name,
                            submitter_roles,
                            "active",
                            organisation_id,
                            draft.get("auth_provider") or "streamlit",
                        ),
                    )
                    self._upsert_organisation_and_membership(
                        cur,
                        organisation_id,
                        organisation_name,
                        submitter_email,
                        submitter_roles,
                        "active",
                    )

                cur.execute(
                    """
                    INSERT INTO app_workflow.audit_events (
                        event_id,
                        event_type,
                        organisation_id,
                        actor_email,
                        actor_name,
                        actor_roles,
                        entity_type,
                        entity_id,
                        event_payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        "preference_card_draft_submitted",
                        organisation_id,
                        submitter_email,
                        submitter_name,
                        submitter_roles,
                        "preference_card_draft",
                        draft.get("draft_id"),
                        Json(_json_safe(event_payload)),
                    ),
                )
            conn.commit()

    def record_draft_review_decision(
        self,
        review: Dict[str, Any],
        blob_review_key: Optional[str] = None,
    ) -> None:
        if not self.enabled:
            return

        reviewer_email = review.get("reviewer_email") or None
        reviewer_name = review.get("reviewer") or "Unknown reviewer"
        reviewer_roles = list(review.get("reviewer_roles") or [])
        organisation_id = _safe_organisation_id(review.get("organisation_id"))
        organisation_name = _safe_organisation_name(review.get("organisation_name"))

        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app_workflow.organisations (
                        organisation_id,
                        organisation_name,
                        status
                    )
                    VALUES (%s, %s, 'active')
                    ON CONFLICT (organisation_id)
                    DO UPDATE SET organisation_name = EXCLUDED.organisation_name,
                                  updated_at = CURRENT_TIMESTAMP
                    """,
                    (organisation_id, organisation_name),
                )
                if reviewer_email:
                    cur.execute(
                        """
                        INSERT INTO app_workflow.app_users (
                            user_email,
                            display_name,
                            roles,
                            status,
                            default_organisation_id,
                            auth_provider,
                            last_seen_at
                        )
                        VALUES (%s, %s, %s, 'active', %s, 'streamlit', CURRENT_TIMESTAMP)
                        ON CONFLICT (user_email)
                        DO UPDATE SET display_name = EXCLUDED.display_name,
                                      roles = CASE
                                          WHEN app_workflow.app_users.status = 'suspended'
                                          THEN app_workflow.app_users.roles
                                          ELSE EXCLUDED.roles
                                      END,
                                      status = CASE
                                          WHEN app_workflow.app_users.status = 'suspended'
                                          THEN app_workflow.app_users.status
                                          ELSE 'active'
                                      END,
                                      default_organisation_id = EXCLUDED.default_organisation_id,
                                      auth_provider = EXCLUDED.auth_provider,
                                      last_seen_at = CURRENT_TIMESTAMP,
                                      updated_at = CURRENT_TIMESTAMP
                        """,
                        (reviewer_email, reviewer_name, reviewer_roles, organisation_id),
                    )
                    self._upsert_organisation_and_membership(
                        cur,
                        organisation_id,
                        organisation_name,
                        reviewer_email,
                        reviewer_roles,
                        "active",
                    )

                cur.execute(
                    """
                    INSERT INTO app_workflow.draft_reviews (
                        review_id,
                        organisation_id,
                        draft_id,
                        draft_object_key,
                        blob_review_key,
                        draft_type,
                        decision,
                        reviewer_name,
                        reviewer_email,
                        reviewer_roles,
                        comments,
                        reviewed_at,
                        source_gold_key,
                        surgeon_id,
                        surgeon_name,
                        procedure,
                        procedure_id,
                        review_payload
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (review_id)
                    DO UPDATE SET organisation_id = EXCLUDED.organisation_id,
                                  draft_id = EXCLUDED.draft_id,
                                  draft_object_key = EXCLUDED.draft_object_key,
                                  blob_review_key = EXCLUDED.blob_review_key,
                                  draft_type = EXCLUDED.draft_type,
                                  decision = EXCLUDED.decision,
                                  reviewer_name = EXCLUDED.reviewer_name,
                                  reviewer_email = EXCLUDED.reviewer_email,
                                  reviewer_roles = EXCLUDED.reviewer_roles,
                                  comments = EXCLUDED.comments,
                                  reviewed_at = EXCLUDED.reviewed_at,
                                  source_gold_key = EXCLUDED.source_gold_key,
                                  surgeon_id = EXCLUDED.surgeon_id,
                                  surgeon_name = EXCLUDED.surgeon_name,
                                  procedure = EXCLUDED.procedure,
                                  procedure_id = EXCLUDED.procedure_id,
                                  review_payload = EXCLUDED.review_payload
                    """,
                    (
                        review["review_id"],
                        organisation_id,
                        review.get("draft_id"),
                        review.get("draft_object_key"),
                        blob_review_key,
                        review.get("draft_type"),
                        review["decision"],
                        reviewer_name,
                        reviewer_email,
                        reviewer_roles,
                        review.get("comments"),
                        review["reviewed_at"],
                        review.get("source_gold_key"),
                        review.get("surgeon_id"),
                        review.get("surgeon_name"),
                        review.get("procedure"),
                        review.get("procedure_id"),
                        Json(_json_safe(review)),
                    ),
                )

                cur.execute(
                    """
                    INSERT INTO app_workflow.audit_events (
                        event_id,
                        event_type,
                        organisation_id,
                        actor_email,
                        actor_name,
                        actor_roles,
                        entity_type,
                        entity_id,
                        event_payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        "draft_review_decision_recorded",
                        organisation_id,
                        reviewer_email,
                        reviewer_name,
                        reviewer_roles,
                        "preference_card_draft",
                        review.get("draft_id"),
                        Json(_json_safe(review)),
                    ),
                )
            conn.commit()

    def record_publish_event(self, publish_event: Dict[str, Any], event_object_key: str) -> None:
        if not self.enabled:
            return

        event_payload = {**publish_event, "event_object_key": event_object_key}
        organisation_id = _safe_organisation_id(publish_event.get("organisation_id"))
        organisation_name = _safe_organisation_name(publish_event.get("organisation_name"))
        with psycopg2.connect(self.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app_workflow.organisations (
                        organisation_id,
                        organisation_name,
                        status
                    )
                    VALUES (%s, %s, 'active')
                    ON CONFLICT (organisation_id)
                    DO UPDATE SET organisation_name = EXCLUDED.organisation_name,
                                  updated_at = CURRENT_TIMESTAMP
                    """,
                    (organisation_id, organisation_name),
                )
                cur.execute(
                    """
                    INSERT INTO app_workflow.audit_events (
                        event_id,
                        event_type,
                        organisation_id,
                        actor_email,
                        actor_name,
                        actor_roles,
                        entity_type,
                        entity_id,
                        event_payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        "approved_draft_published_to_gold",
                        organisation_id,
                        publish_event.get("publisher_email"),
                        publish_event.get("publisher"),
                        list(publish_event.get("publisher_roles") or []),
                        "preference_card_draft",
                        publish_event.get("draft_id"),
                        Json(_json_safe(event_payload)),
                    ),
                )
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
