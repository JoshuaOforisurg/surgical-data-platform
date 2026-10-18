"""Disposable local Postgres test for cross-tenant preference-card isolation."""

from __future__ import annotations

import os
import uuid
from dataclasses import replace

import psycopg2
import pytest
from psycopg2 import sql

from config.settings import load_settings
from bronze_Ingestion.catalog import BronzeCatalogRepository
from streamlit_services.preference_card_repository import PreferenceCardRepository


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LOCAL_TENANT_INTEGRATION") != "1",
    reason="Set RUN_LOCAL_TENANT_INTEGRATION=1 to use a disposable local Postgres database.",
)


def test_preference_reads_and_history_do_not_cross_organisation_boundaries():
    base = load_settings()
    if (
        not base.postgres
        or base.postgres.host not in {"localhost", "127.0.0.1", "::1"}
        or os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    ):
        pytest.fail("Integration test requires local Postgres and no Azure storage setting.")

    database_name = f"sp_tenant_test_{uuid.uuid4().hex[:12]}"
    admin_settings = replace(base.postgres, database="postgres")
    created = False
    try:
        admin_conn = psycopg2.connect(admin_settings.psycopg2_dsn)
        admin_conn.autocommit = True
        try:
            with admin_conn.cursor() as cur:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
        finally:
            admin_conn.close()
        created = True

        repository = PreferenceCardRepository(
            replace(base.postgres, database=database_name)
        )
        repository.initialise()
        repository.import_gold_rows(
            rows=[{
                "surgeon_id": "SURG-A",
                "surgeon_name": "Surgeon Tenant A",
                "procedure_id": "PROC-A",
                "procedure": "Total Hip Replacement",
                "instrument_set": "Tenant A hip set",
            }],
            source_gold_key="integration/tenant-a.csv",
            organisation_id="hospital-a",
            organisation_name="Hospital A",
        )
        repository.import_gold_rows(
            rows=[{
                "surgeon_id": "SURG-B",
                "surgeon_name": "Surgeon Tenant B",
                "procedure_id": "PROC-B",
                "procedure": "Total Knee Replacement",
                "instrument_set": "Tenant B knee set",
            }],
            source_gold_key="integration/tenant-b.csv",
            organisation_id="hospital-b",
            organisation_name="Hospital B",
        )

        with psycopg2.connect(repository.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                for email, name, organisation_id, roles in (
                    ("staff-a@example.test", "Staff A", "hospital-a", ["authenticated", "editor"]),
                    ("staff-b@example.test", "Staff B", "hospital-b", ["authenticated", "editor"]),
                    ("admin-a@example.test", "Admin A", "hospital-a", ["authenticated", "admin"]),
                ):
                    cur.execute(
                        """
                        INSERT INTO app_workflow.app_users (user_email, display_name, status)
                        VALUES (%s, %s, 'active') ON CONFLICT (user_email) DO NOTHING
                        """,
                        (email, name),
                    )
                    cur.execute(
                        """
                        INSERT INTO app_workflow.organisation_memberships
                            (organisation_id, user_email, roles, status)
                        VALUES (%s, %s, %s, 'active')
                        ON CONFLICT (organisation_id, user_email) DO UPDATE
                        SET roles = EXCLUDED.roles, status = 'active'
                        """,
                        (organisation_id, email, roles),
                    )

        workflow = BronzeCatalogRepository(repository.settings)
        workflow.record_draft_submission(
            {
                "draft_id": "tenant-a-draft",
                "draft_type": "edit",
                "organisation_id": "hospital-a",
                "submitted_by": "Staff A",
                "submitter_email": "staff-a@example.test",
                "submitter_roles": ["authenticated", "editor"],
            },
            "organisations/hospital-a/drafts/tenant-a-draft.json",
        )
        with pytest.raises(PermissionError, match="active membership"):
            workflow.record_draft_submission(
                {
                    "draft_id": "forged-tenant-b-draft",
                    "draft_type": "edit",
                    "organisation_id": "hospital-b",
                    "submitted_by": "Staff A",
                    "submitter_email": "staff-a@example.test",
                    "submitter_roles": ["authenticated", "editor"],
                },
                "organisations/hospital-b/drafts/forged.json",
            )

        card_draft = {
            "status": "approved_pending_publish",
            "draft_type": "edit",
            "surgeon_id": "SURG-A",
            "surgeon_name": "Surgeon Tenant A",
            "procedure_id": "PROC-A",
            "procedure": "Total Hip Replacement",
            "proposed": {"consumables": "Tenant A hip pack"},
        }
        with pytest.raises(PermissionError, match="required organisation role"):
            repository.publish_approved_draft(
                draft=card_draft,
                publisher="staff-a@example.test",
                editable_fields=["consumables"],
                source_gold_key="integration/hospital-a.csv",
                organisation_id="hospital-a",
            )
        published = repository.publish_approved_draft(
            draft=card_draft,
            publisher="admin-a@example.test",
            editable_fields=["consumables"],
            source_gold_key="integration/hospital-a.csv",
            organisation_id="hospital-a",
        )
        history = repository.list_card_history(
            surgeon_name="Surgeon Tenant A",
            procedure_name="Total Hip Replacement",
            organisation_id="hospital-a",
        )
        initial_version_id = next(
            row["version_id"] for row in history if int(row["version_number"]) == 1
        )
        with pytest.raises(PermissionError, match="required organisation role"):
            repository.rollback_to_version(
                card_id=published.card_id,
                source_version_id=initial_version_id,
                actor_email="staff-a@example.test",
                actor_name="Staff A",
                actor_roles=["authenticated", "editor"],
                reason="Test denied rollback",
                source_gold_key="integration/hospital-a.csv",
                organisation_id="hospital-a",
            )
        rollback = repository.rollback_to_version(
            card_id=published.card_id,
            source_version_id=initial_version_id,
            actor_email="admin-a@example.test",
            actor_name="Admin A",
            actor_roles=["authenticated", "admin"],
            reason="Restore baseline for tenant isolation test",
            source_gold_key="integration/hospital-a.csv",
            organisation_id="hospital-a",
        )
        assert rollback.rolled_back
        with pytest.raises(PermissionError, match="required organisation role"):
            workflow.update_app_user_access(
                user_email="staff-b@example.test",
                display_name="Staff B",
                roles=["authenticated", "admin"],
                status="active",
                actor_email="staff-a@example.test",
                actor_name="Staff A",
                actor_roles=["admin"],
                organisation_id="hospital-a",
            )

        tenant_a_cards = repository.list_current_cards(organisation_id="hospital-a")
        tenant_b_cards = repository.list_current_cards(organisation_id="hospital-b")
        leaked_history = repository.list_card_history(
            surgeon_name="Surgeon Tenant B",
            procedure_name="Total Knee Replacement",
            organisation_id="hospital-a",
        )

        assert [card["surgeon_name"] for card in tenant_a_cards] == ["Surgeon Tenant A"]
        assert [card["surgeon_name"] for card in tenant_b_cards] == ["Surgeon Tenant B"]
        assert leaked_history == []
    finally:
        if created:
            admin_conn = psycopg2.connect(admin_settings.psycopg2_dsn)
            admin_conn.autocommit = True
            try:
                with admin_conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                            sql.Identifier(database_name)
                        )
                    )
            finally:
                admin_conn.close()
