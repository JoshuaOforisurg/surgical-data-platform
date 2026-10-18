from unittest.mock import MagicMock
import uuid

import pytest

from bronze_Ingestion.catalog import BronzeCatalogRepository
from config.settings import PostgresSettings


@pytest.fixture
def catalog(monkeypatch):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor = connection.cursor.return_value.__enter__.return_value
    monkeypatch.setattr("bronze_Ingestion.catalog.psycopg2.connect", lambda _: connection)
    def require_test_actor(_cursor, email, _org, _roles):
        if not email:
            raise PermissionError("actor required")

    monkeypatch.setattr("bronze_Ingestion.catalog.assert_active_membership_roles", require_test_actor)
    repository = BronzeCatalogRepository(PostgresSettings("localhost", 5433, "test", "test", "test"))
    return repository, cursor, connection


def statement(cursor, fragment):
    matches = [call.args for call in cursor.execute.call_args_list if fragment in call.args[0]]
    assert len(matches) == 1
    return matches[0]


def test_submission_persists_draft_without_rewinding_existing_status(catalog):
    repository, cursor, connection = catalog
    repository.record_draft_submission({
        "draft_id": "draft-1", "draft_type": "edit", "organisation_id": "hospital-a",
        "submitter_email": "editor@example.com",
        "original": {"consumables": "Original"}, "proposed": {"consumables": "Revised"},
    }, "gold/operational/drafts/draft-1.json")
    sql, params = statement(cursor, "INSERT INTO app_workflow.preference_card_drafts")
    assert "ON CONFLICT (draft_id) DO NOTHING" in sql
    assert "'pending_review'" in sql
    assert params[:3] == ("draft-1", "hospital-a", "edit")
    assert params[3].adapted == {"consumables": "Original"}
    assert params[4].adapted == {"consumables": "Revised"}
    assert params[7] == "gold/operational/drafts/draft-1.json"
    connection.commit.assert_called_once()


def test_run_retry_does_not_reset_existing_run(catalog):
    repository, cursor, connection = catalog
    cursor.fetchone.return_value = ("run-1",)
    repository.start_run("run-1", "/source", "v1", "v1")
    sql, params = statement(cursor, "INSERT INTO pipeline_audit.pipeline_runs")
    assert "ON CONFLICT (run_id) DO NOTHING" in sql
    assert params == ("run-1", "running", "/source", "v1", "v1", None)
    connection.commit.assert_called_once()


def test_membership_lookup_uses_requested_organisation_and_active_org(catalog):
    repository, cursor, _ = catalog
    cursor.fetchone.return_value = {
        "user_email": "person@example.com",
        "organisation_id": "hospital-a",
        "roles": ["authenticated", "editor"],
        "status": "active",
    }

    membership = repository.get_user_membership("Person@Example.com", "hospital-a")

    sql, params = statement(cursor, "FROM app_workflow.organisation_memberships memberships")
    assert "memberships.organisation_id = %s" in sql
    assert "organisations.status = 'active'" in sql
    assert params == ("Person@Example.com", "hospital-a")
    assert membership["roles"] == ["authenticated", "editor"]


def test_membership_lookup_cannot_return_another_tenant_membership(catalog):
    repository, cursor, _ = catalog
    cursor.fetchone.return_value = None

    membership = repository.get_user_membership("person@example.com", "hospital-b")

    sql, params = statement(cursor, "FROM app_workflow.organisation_memberships memberships")
    assert "memberships.organisation_id = %s" in sql
    assert params == ("person@example.com", "hospital-b")
    assert membership is None


def test_identity_seen_upsert_persists_provider_qualified_subject(catalog):
    repository, cursor, connection = catalog
    cursor.fetchone.side_effect = [None, {"user_email": "person@example.com"}]

    repository.upsert_app_user_seen(
        user_email="Person@Example.com",
        display_name="Person",
        auth_provider="AAD",
        identity_subject="subject-123",
    )

    lookup_sql, lookup_params = cursor.execute.call_args_list[0].args
    assert "auth_provider = %s AND identity_subject = %s" in lookup_sql
    assert lookup_params == ("aad", "subject-123")
    insert_sql, insert_params = cursor.execute.call_args_list[1].args
    assert "identity_subject" in insert_sql
    assert "uq_app_users_provider_subject" not in insert_sql
    assert insert_params == ("person@example.com", "Person", "aad", "subject-123")
    connection.commit.assert_called_once()


def test_identity_subject_cannot_be_silently_linked_to_a_different_email(catalog):
    repository, cursor, connection = catalog
    cursor.fetchone.return_value = {"user_email": "old@example.com"}

    with pytest.raises(ValueError, match="already linked to another registry account"):
        repository.upsert_app_user_seen(
            user_email="new@example.com",
            display_name="Person",
            auth_provider="aad",
            identity_subject="subject-123",
        )

    assert cursor.execute.call_count == 1
    connection.commit.assert_not_called()


def test_user_membership_listing_supports_multiple_organisations(catalog):
    repository, cursor, _ = catalog
    cursor.fetchall.return_value = [
        {"organisation_id": "hospital-a", "roles": ["editor"], "status": "active"},
        {"organisation_id": "hospital-b", "roles": ["reviewer"], "status": "active"},
    ]

    memberships = repository.list_user_memberships("person@example.com")

    sql, params = statement(cursor, "FROM app_workflow.organisation_memberships memberships")
    assert "lower(memberships.user_email) = lower(%s)" in sql
    assert params == ("person@example.com",)
    assert [row["organisation_id"] for row in memberships] == ["hospital-a", "hospital-b"]


def test_access_update_writes_roles_to_membership_not_global_user(catalog):
    repository, cursor, connection = catalog
    cursor.fetchone.side_effect = [
        (1,),
        {"user_email": "person@example.com"},
        {
            "user_email": "person@example.com",
            "organisation_id": "hospital-a",
            "roles": ["authenticated", "editor"],
            "status": "active",
        },
    ]

    result = repository.update_app_user_access(
        user_email="person@example.com",
        display_name="Person",
        roles=["editor"],
        status="active",
        actor_email="admin@example.com",
        actor_name="Admin",
        actor_roles=["admin"],
        organisation_id="hospital-a",
        organisation_name="Hospital A",
    )

    sql, params = statement(cursor, "INSERT INTO app_workflow.organisation_memberships")
    assert "ON CONFLICT (organisation_id, user_email)" in sql
    assert params == ("hospital-a", "person@example.com", ["authenticated", "editor"], "active")
    user_upsert_sql, _ = statement(cursor, "INSERT INTO app_workflow.app_users")
    assert "roles" not in user_upsert_sql.split("ON CONFLICT", 1)[0]
    assert result["organisation_id"] == "hospital-a"
    connection.commit.assert_called_once()


def test_access_request_resolution_is_scoped_to_organisation(catalog):
    repository, cursor, connection = catalog
    request_row = {
        "access_request_id": "request-1",
        "organisation_id": "hospital-a",
        "user_email": "person@example.com",
        "display_name": "Person",
        "requested_roles": ["authenticated", "editor"],
        "requested_organisation_name": "Hospital A",
        "reason": "Theatre staff",
        "status": "pending_review",
    }
    cursor.fetchone.side_effect = [request_row, {**request_row, "status": "approved"}]

    repository.resolve_access_request(
        access_request_id="request-1",
        organisation_id="hospital-a",
        decision="approved",
        actor_email="admin@example.com",
        actor_name="Admin",
        actor_roles=["admin"],
    )

    sql, params = statement(cursor, "SELECT\n                        access_request_id")
    assert "AND organisation_id = %s" in sql
    assert "AND status = 'pending_review'" in sql
    assert params == ("request-1", "hospital-a")
    connection.commit.assert_called_once()


def test_existing_run_id_is_rejected_instead_of_restarted(catalog):
    repository, cursor, connection = catalog
    cursor.fetchone.return_value = None
    with pytest.raises(ValueError, match="already exists"):
        repository.start_run("run-1", "/source", "v1", "v1")
    assert "DO NOTHING" in statement(cursor, "INSERT INTO pipeline_audit.pipeline_runs")[0]
    connection.commit.assert_not_called()


def test_file_registration_reuses_catalog_identity_for_same_landing_key(catalog):
    repository, cursor, connection = catalog
    cursor.fetchone.return_value = ("00000000-0000-0000-0000-000000000123",)
    file_id = repository.register_file({
        "run_id": "run-2", "bucket": "source", "object_key": "landing/content/hash/card.json",
        "object_uri": "s3://source/landing/content/hash/card.json", "original_filename": "card.json",
        "file_extension": "json", "checksum_sha256": "hash",
    })
    sql, _ = statement(cursor, "INSERT INTO bronze_raw.ingested_files")
    assert "ON CONFLICT (bucket, object_key)" in sql
    assert str(file_id) == "00000000-0000-0000-0000-000000000123"
    connection.commit.assert_called_once()


def test_stage_record_captures_status_and_reconciled_counts(catalog):
    repository, cursor, connection = catalog
    repository.record_stage(
        "run-3", "silver_b", "completed", records_received=100,
        records_processed=100, records_rejected=7, completed=True,
    )
    sql, params = statement(cursor, "INSERT INTO pipeline_audit.pipeline_run_stages")
    assert "ON CONFLICT (run_id, stage_name)" in sql
    assert params == ("run-3", "silver_b", "completed", 100, 100, 7, None, True, True)
    connection.commit.assert_called_once()


def test_bronze_record_ids_are_stable_for_file_and_ordinal(monkeypatch):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor = connection.cursor.return_value.__enter__.return_value
    values_written = []
    sql_written = []
    monkeypatch.setattr("bronze_Ingestion.catalog.psycopg2.connect", lambda _: connection)
    monkeypatch.setattr(
        "bronze_Ingestion.catalog.execute_values",
        lambda _cursor, sql, values: (sql_written.append(sql), values_written.append(values)),
    )
    repository = BronzeCatalogRepository(PostgresSettings("localhost", 5433, "test", "test", "test"))
    file_id = uuid.UUID("00000000-0000-0000-0000-000000000123")
    for run_id in ("run-a", "run-b"):
        repository.write_records(file_id, run_id, [{"value": 1}, {"value": 2}])

    assert [row[0] for row in values_written[0]] == [row[0] for row in values_written[1]]
    assert "ON CONFLICT (file_id, record_ordinal)" in sql_written[0]
    assert connection.commit.call_count == 2


def test_run_file_links_each_execution_to_reused_source_file(catalog):
    repository, cursor, connection = catalog
    file_id = uuid.UUID("00000000-0000-0000-0000-000000000123")
    repository.register_run_file("run-replay", file_id)
    sql, params = statement(cursor, "INSERT INTO pipeline_audit.pipeline_run_files")
    assert "ON CONFLICT (run_id, file_id) DO NOTHING" in sql
    assert params == ("run-replay", str(file_id))
    connection.commit.assert_called_once()


def test_run_file_lookup_only_returns_sources_for_failed_runs(catalog):
    repository, cursor, _ = catalog
    cursor.fetchall.return_value = [{
        "file_id": "00000000-0000-0000-0000-000000000123",
        "object_key": "landing/source.json",
        "original_filename": "source.json",
        "checksum_sha256": "checksum",
    }]
    rows = repository.get_run_files("failed-run")
    sql, params = statement(cursor, "FROM pipeline_audit.pipeline_run_files")
    assert "runs.status = 'failed'" in sql
    assert params == ("failed-run",)
    assert rows[0]["object_key"] == "landing/source.json"


@pytest.mark.parametrize("decision,status", [
    ("approved", "approved_pending_publish"),
    ("needs_changes", "changes_requested"),
    ("rejected", "rejected"),
])
def test_review_updates_only_pending_draft_in_its_organisation(catalog, decision, status):
    repository, cursor, connection = catalog
    repository.record_draft_review_decision({
        "review_id": "review-1", "draft_id": "draft-1", "decision": decision,
        "reviewer": "Reviewer", "reviewed_at": "2026-10-17T10:00:00Z",
        "reviewer_email": "reviewer@example.com",
        "organisation_id": "hospital-a",
    })
    sql, params = statement(cursor, "UPDATE app_workflow.preference_card_drafts")
    assert "organisation_id = %s AND status = 'pending_review'" in sql
    assert params[0] == status
    assert params[-2:] == ("draft-1", "hospital-a")
    connection.commit.assert_called_once()


def publication(**changes):
    return {
        "publish_id": "publish-1", "draft_id": "draft-1", "card_id": "card-1",
        "version_id": "version-2", "organisation_id": "hospital-a",
        "published_at": "2026-10-17T11:00:00Z", "publisher_email": "admin@example.invalid",
        "published_gold_key": "gold/operational/published/publish-1/cards.csv",
        **changes,
    }


def test_publish_records_exact_version_and_updates_only_approved_draft(catalog):
    repository, cursor, connection = catalog
    cursor.fetchone.return_value = (1,)
    repository.record_publish_event(publication(), "events/publish-1.json")
    _, params = statement(cursor, "SELECT 1 FROM app_workflow.preference_card_versions")
    assert params == ("card-1", "version-2", "hospital-a")
    sql, params = statement(cursor, "INSERT INTO app_workflow.preference_card_publish_events")
    assert "ON CONFLICT (publish_id) DO NOTHING" in sql
    assert params[:5] == ("publish-1", "hospital-a", "card-1", "version-2", "draft-1")
    sql, params = statement(cursor, "UPDATE app_workflow.preference_card_drafts")
    assert "organisation_id = %s AND status = 'approved_pending_publish'" in sql
    assert params[-2:] == ("draft-1", "hospital-a")
    connection.commit.assert_called_once()


def test_publish_rejects_version_outside_card_or_organisation(catalog):
    repository, cursor, connection = catalog
    cursor.fetchone.return_value = None
    with pytest.raises(ValueError, match="card and organisation"):
        repository.record_publish_event(publication(), "events/publish-1.json")
    assert not any("INSERT" in call.args[0] for call in cursor.execute.call_args_list)
    connection.commit.assert_not_called()


def test_rollback_event_links_rollback_version_without_a_draft(catalog):
    repository, cursor, _ = catalog
    cursor.fetchone.return_value = (1,)
    repository.record_publish_event(publication(
        draft_id=None, version_id=None, rollback_version_id="version-3",
        event_type="preference_card_rollback_published",
    ), "events/rollback-1.json")
    _, params = statement(cursor, "INSERT INTO app_workflow.preference_card_publish_events")
    assert params[2:5] == ("card-1", "version-3", None)
    _, params = statement(cursor, "INSERT INTO app_workflow.audit_events")
    assert params[1] == "preference_card_rollback_published"
    assert params[6:8] == ("preference_card", "card-1")
