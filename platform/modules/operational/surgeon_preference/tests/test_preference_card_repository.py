import pytest
from unittest.mock import MagicMock

from streamlit_services.preference_card_repository import (
    PreferenceCardRepository,
    build_published_card_payload,
    card_key_for_row,
    current_card_rows_to_dataframe,
    normalise_gold_card_row,
    _same_imported_card_content,
)


def test_card_key_prefers_ids_and_is_stable():
    row = {
        "surgeon_id": "SURG-001",
        "surgeon_name": "Changed Name",
        "procedure_id": "ORTH_HIP_001",
        "procedure": "Changed Procedure",
    }

    assert card_key_for_row(row) == card_key_for_row(
        {
            "surgeon_id": "SURG-001",
            "surgeon_name": "Another Name",
            "procedure_id": "ORTH_HIP_001",
            "procedure": "Another Procedure",
        }
    )


def test_card_key_falls_back_to_names_for_legacy_rows():
    row = {
        "surgeon_name": "Ms Amina Clarke",
        "procedure": "Total Knee Replacement",
    }

    assert card_key_for_row(row).startswith("card_")
    assert card_key_for_row(row) == card_key_for_row(
        {
            "surgeon_name": "Ms Amina Clarke",
            "procedure_name": "Total Knee Replacement",
        }
    )


def test_normalise_gold_card_row_maps_current_gold_shape_to_product_shape():
    row = normalise_gold_card_row(
        {
            "surgeon_id": "SURG-001",
            "surgeon_name": "  Ms Amina Clarke ",
            "procedure_id": "ORTH_KNEE_001",
            "procedure": " Total Knee Replacement ",
            "specialty": "Orthopaedics",
            "subspecialty": "Knee",
            "preference_card_version": "3",
        }
    )

    assert row["surgeon_name"] == "Ms Amina Clarke"
    assert row["procedure_name"] == "Total Knee Replacement"
    assert row["version_number"] == 3
    assert row["version_label"] == "v3"
    assert row["card_key"].startswith("card_")


def test_normalise_gold_card_row_rejects_missing_identity():
    with pytest.raises(ValueError, match="surgeon_name"):
        normalise_gold_card_row({"procedure": "Total Hip Replacement"})

    with pytest.raises(ValueError, match="procedure"):
        normalise_gold_card_row({"surgeon_name": "Mr Test Surgeon"})


def test_import_content_comparison_ignores_only_per_run_gold_timestamp():
    baseline = {"consumables": "Hip pack", "gold_created_at": "2026-01-01T00:00:00Z"}
    assert _same_imported_card_content(
        baseline,
        {"consumables": "Hip pack", "gold_created_at": "2026-01-02T00:00:00Z"},
    )
    assert not _same_imported_card_content(
        baseline,
        {"consumables": "Knee pack", "gold_created_at": "2026-01-02T00:00:00Z"},
    )


def test_repository_is_noop_when_postgres_is_not_configured():
    repository = PreferenceCardRepository(settings=None)

    summary = repository.import_gold_rows(
        rows=[
            {
                "surgeon_name": "Ms Amina Clarke",
                "procedure": "Total Knee Replacement",
            }
        ],
        source_gold_key="gold/operational/latest/gold_operational_preference_cards.csv",
    )

    assert summary.enabled is False
    assert summary.imported == 0
    assert repository.list_current_cards() == []
    assert repository.list_card_history(
        surgeon_name="Ms Amina Clarke",
        procedure_name="Total Knee Replacement",
    ) == []
    publish_summary = repository.publish_approved_draft(
        draft={
            "status": "approved_pending_publish",
            "draft_type": "edit",
            "surgeon_name": "Ms Amina Clarke",
            "procedure": "Total Knee Replacement",
            "proposed": {"equipment": "Tourniquet and image intensifier"},
        },
        publisher="Clinical Admin",
        editable_fields=["equipment"],
        source_gold_key="gold/operational/latest/gold_operational_preference_cards.csv",
    )
    assert publish_summary.enabled is False
    assert publish_summary.published is False
    rollback_summary = repository.rollback_to_version(
        card_id="00000000-0000-0000-0000-000000000001",
        source_version_id="00000000-0000-0000-0000-000000000002",
        actor_email="admin@example.com",
        actor_name="Admin",
        actor_roles=["admin"],
        reason="Incorrect preference card published.",
        source_gold_key="gold/operational/latest/gold_operational_preference_cards.csv",
    )
    assert rollback_summary.enabled is False
    assert rollback_summary.rolled_back is False


@pytest.mark.parametrize("organisation_id", ["hospital-a", "hospital-b"])
def test_current_card_reads_are_scoped_to_the_requested_tenant(monkeypatch, organisation_id):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [{
        "organisation_id": organisation_id,
        "surgeon_name": f"Surgeon for {organisation_id}",
    }]
    monkeypatch.setattr(
        "streamlit_services.preference_card_repository.psycopg2.connect",
        lambda _: connection,
    )
    repository = PreferenceCardRepository(
        settings=type("Settings", (), {"psycopg2_dsn": "postgresql://test"})()
    )

    rows = repository.list_current_cards(organisation_id=organisation_id)

    sql, params = cursor.execute.call_args.args
    assert "WHERE cards.organisation_id = %s" in sql
    assert params == (organisation_id, "active", 500)
    assert {row["organisation_id"] for row in rows} == {organisation_id}


def test_pipeline_import_preserves_staff_published_current_card(monkeypatch):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {
        "card_key": "existing-key",
        "current_version_number": 4,
        "card_payload": {"equipment": "Staff-approved equipment"},
        "change_type": "draft_publish",
    }
    monkeypatch.setattr(
        "streamlit_services.preference_card_repository.psycopg2.connect",
        lambda _: connection,
    )
    repository = PreferenceCardRepository(
        settings=type("Settings", (), {"psycopg2_dsn": "postgresql://test"})()
    )
    result = repository.import_gold_rows(
        rows=[{"surgeon_name": "Ms Amina Clarke", "procedure": "Total Knee Replacement"}],
        source_gold_key="gold/operational/latest/cards.csv",
    )

    assert result.imported == 0
    assert result.protected == 1
    assert result.unchanged == 0
    assert not any(
        "INSERT INTO app_workflow.preference_cards" in call.args[0]
        for call in cursor.execute.call_args_list
    )


def test_current_card_rows_to_dataframe_matches_frontend_shape():
    df = current_card_rows_to_dataframe(
        [
            {
                "card_id": "card-uuid",
                "card_key": "card_123",
                "surgeon_id": "SURG-001",
                "surgeon_name": "Ms Amina Clarke",
                "procedure_id": "ORTH_KNEE_001",
                "procedure_name": "Total Knee Replacement",
                "specialty": "Orthopaedics",
                "subspecialty": "Knee",
                "current_version_number": 4,
                "card_payload": {
                    "instrument_set": "Primary knee set",
                    "equipment": "Tourniquet",
                    "preference_card_version_label": "v4",
                },
                "source_gold_key": "gold/operational/latest/gold_operational_preference_cards.csv",
                "published_by": "pipeline",
                "published_at": "2026-10-07T10:00:00+00:00",
            }
        ]
    )

    row = df.iloc[0]
    assert row["surgeon_name"] == "Ms Amina Clarke"
    assert row["procedure"] == "Total Knee Replacement"
    assert row["preference_card_version"] == 4
    assert row["preference_card_version_label"] == "v4"
    assert row["instrument_set"] == "Primary knee set"
    assert row["operational_source"] == "postgres"


def test_build_published_card_payload_updates_edit_and_bumps_version():
    payload = build_published_card_payload(
        current_payload={
            "surgeon_id": "SURG-001",
            "surgeon_name": "Ms Amina Clarke",
            "procedure_id": "ORTH_KNEE_001",
            "procedure": "Total Knee Replacement",
            "equipment": "Tourniquet",
            "preference_card_version": 2,
        },
        draft={
            "status": "approved_pending_publish",
            "draft_type": "edit",
            "surgeon_name": "Ms Amina Clarke",
            "procedure": "Total Knee Replacement",
            "proposed": {
                "equipment": "Tourniquet and image intensifier",
                "implants": "Cemented knee system",
            },
        },
        publisher="Clinical Admin",
        editable_fields=["equipment"],
        published_at="2026-10-07T11:00:00+00:00",
    )

    assert payload["equipment"] == "Tourniquet and image intensifier"
    assert "implants" not in payload
    assert payload["version_number"] == 3
    assert payload["preference_card_version_label"] == "v3"
    assert payload["version_updated_by"] == "Clinical Admin"


def test_build_published_card_payload_creates_new_card_version_one():
    payload = build_published_card_payload(
        current_payload={},
        draft={
            "status": "approved_pending_publish",
            "draft_type": "create",
            "surgeon_id": "SURG-002",
            "surgeon_name": "Mr Kwame Mensah",
            "procedure_id": "ORTH_HIP_001",
            "procedure": "Total Hip Replacement",
            "specialty": "Orthopaedics",
            "subspecialty": "Hip",
            "proposed": {"instrument_set": "Primary hip set"},
        },
        publisher="Clinical Admin",
        editable_fields=["instrument_set"],
        published_at="2026-10-07T11:00:00+00:00",
    )

    assert payload["surgeon_name"] == "Mr Kwame Mensah"
    assert payload["procedure_name"] == "Total Hip Replacement"
    assert payload["instrument_set"] == "Primary hip set"
    assert payload["version_number"] == 1
    assert payload["preference_card_version_label"] == "v1"


def test_build_published_card_payload_rejects_unapproved_or_unmatched_edit():
    with pytest.raises(ValueError, match="Only approved_pending_publish"):
        build_published_card_payload(
            current_payload={},
            draft={"status": "pending_review", "draft_type": "create"},
            publisher="Clinical Admin",
            editable_fields=[],
            published_at="2026-10-07T11:00:00+00:00",
        )

    with pytest.raises(ValueError, match="does not match"):
        build_published_card_payload(
            current_payload={},
            draft={
                "status": "approved_pending_publish",
                "draft_type": "edit",
                "surgeon_name": "Ms Amina Clarke",
                "procedure": "Total Knee Replacement",
            },
            publisher="Clinical Admin",
            editable_fields=[],
            published_at="2026-10-07T11:00:00+00:00",
        )
