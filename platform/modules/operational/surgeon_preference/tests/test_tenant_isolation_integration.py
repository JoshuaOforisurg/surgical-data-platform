"""Disposable local Postgres test for cross-tenant preference-card isolation."""

from __future__ import annotations

import os
import uuid
from dataclasses import replace
from datetime import UTC, datetime

import psycopg2
import pytest
from psycopg2 import sql

from config.settings import load_settings
from bronze_Ingestion.catalog import BronzeCatalogRepository
from streamlit_services.preference_card_repository import PreferenceCardRepository
from streamlit_services.access_control import AppUser
from streamlit_services.user_registry_service import (
    resolve_access_request,
    submit_access_request,
)


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
        workspace_repository = BronzeCatalogRepository(repository.settings)
        created_workspace = workspace_repository.create_organisation_for_user(
            organisation_name="Northside Teaching Hospital",
            user_email="founder@example.test",
            display_name="Workspace Founder",
            auth_provider="aad",
            identity_subject="founder-subject",
        )
        repeated_workspace = workspace_repository.create_organisation_for_user(
            organisation_name="Northside Teaching Hospital",
            user_email="founder@example.test",
            display_name="Workspace Founder",
            auth_provider="aad",
            identity_subject="founder-subject",
        )
        assert created_workspace["organisation_id"] == "northside-teaching-hospital"
        assert repeated_workspace["organisation_id"] == created_workspace["organisation_id"]
        founder_membership = workspace_repository.get_user_membership(
            "founder@example.test", created_workspace["organisation_id"]
        )
        assert founder_membership["status"] == "active"
        assert set(founder_membership["roles"]) == {"authenticated", "admin"}
        joiner = AppUser(
            email="new-member@example.test",
            display_name="New Member",
            roles=("authenticated",),
            organisation_id="default",
        )
        join_request, join_error = submit_access_request(
            settings=repository.settings,
            user=joiner,
            requested_roles=["editor"],
            requested_organisation_name="",
            reason="I maintain theatre preference cards.",
            organisation_id=created_workspace["organisation_id"],
        )
        assert join_error is None
        pending_membership = workspace_repository.get_user_membership(
            joiner.email, created_workspace["organisation_id"]
        )
        assert pending_membership["status"] == "pending_access"
        owner = AppUser(
            email="founder@example.test",
            display_name="Workspace Founder",
            roles=("authenticated", "admin"),
            status="active",
            organisation_id=created_workspace["organisation_id"],
            organisation_name=created_workspace["organisation_name"],
        )
        resolved_request, resolve_error = resolve_access_request(
            settings=repository.settings,
            access_request_id=str(join_request["access_request_id"]),
            decision="approved",
            actor=owner,
        )
        assert resolve_error is None
        assert resolved_request["status"] == "approved"
        active_joiner_membership = workspace_repository.get_user_membership(
            joiner.email, created_workspace["organisation_id"]
        )
        assert active_joiner_membership["status"] == "active"
        assert set(active_joiner_membership["roles"]) == {"authenticated", "editor"}
        with psycopg2.connect(repository.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM app_workflow.audit_events
                    WHERE organisation_id = %s AND event_type = 'organisation_created'
                    """,
                    (created_workspace["organisation_id"],),
                )
                assert cur.fetchone()[0] == 1

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
                    ("reviewer-a@example.test", "Reviewer A", "hospital-a", ["authenticated", "reviewer"]),
                    ("reviewer-b@example.test", "Reviewer B", "hospital-b", ["authenticated", "reviewer"]),
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
        request_a = workflow.create_access_request(
            user_email="requester-a@example.test",
            display_name="Requester A",
            requested_roles=["authenticated", "editor"],
            requested_organisation_name="Hospital A",
            reason="I prepare Hospital A cases.",
            organisation_id="hospital-a",
            organisation_name="Hospital A",
        )
        request_b = workflow.create_access_request(
            user_email="requester-b@example.test",
            display_name="Requester B",
            requested_roles=["authenticated", "editor"],
            requested_organisation_name="Hospital B",
            reason="I prepare Hospital B cases.",
            organisation_id="hospital-b",
            organisation_name="Hospital B",
        )
        admin_a_requests = workflow.list_access_requests(
            organisation_id="hospital-a",
            actor_email="admin-a@example.test",
            status="pending_review",
        )
        requester_a_requests = workflow.list_access_requests(
            organisation_id="hospital-a",
            actor_email="requester-a@example.test",
            user_email="requester-a@example.test",
        )
        assert [row["access_request_id"] for row in admin_a_requests] == [
            request_a["access_request_id"]
        ]
        assert [row["access_request_id"] for row in requester_a_requests] == [
            request_a["access_request_id"]
        ]
        with pytest.raises(PermissionError, match="required organisation role"):
            workflow.list_access_requests(
                organisation_id="hospital-b",
                actor_email="staff-a@example.test",
                status="pending_review",
            )
        with pytest.raises(PermissionError, match="required organisation role"):
            workflow.list_access_requests(
                organisation_id="hospital-a",
                actor_email="staff-a@example.test",
                user_email="requester-a@example.test",
            )

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

        review_draft = {
            "draft_id": "tenant-a-review-draft",
            "draft_type": "edit",
            "organisation_id": "hospital-a",
            "submitted_by": "Staff A",
            "submitter_email": "staff-a@example.test",
            "submitter_roles": ["authenticated", "editor"],
            "proposed": {"consumables": "Hospital A review sample"},
        }
        workflow.record_draft_submission(
            review_draft,
            "organisations/hospital-a/drafts/tenant-a-review-draft.json",
        )
        review_payload = {
            "review_id": str(uuid.uuid4()),
            "draft_id": review_draft["draft_id"],
            "draft_type": "edit",
            "decision": "approved",
            "reviewer": "Reviewer B",
            "reviewer_email": "reviewer-b@example.test",
            "reviewer_roles": ["authenticated", "reviewer"],
            "reviewed_at": datetime.now(UTC).isoformat(),
            "organisation_id": "hospital-a",
            "organisation_name": "Hospital A",
        }
        with pytest.raises(PermissionError, match="active membership"):
            workflow.record_draft_review_decision(review_payload)

        review_payload.update(
            reviewer="Reviewer A",
            reviewer_email="reviewer-a@example.test",
        )
        workflow.record_draft_review_decision(review_payload)
        with psycopg2.connect(repository.settings.psycopg2_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status FROM app_workflow.preference_card_drafts
                    WHERE draft_id = %s AND organisation_id = %s
                    """,
                    (review_draft["draft_id"], "hospital-a"),
                )
                assert cur.fetchone()[0] == "approved_pending_publish"

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
