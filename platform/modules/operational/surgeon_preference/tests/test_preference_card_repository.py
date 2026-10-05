import pytest

from streamlit_services.preference_card_repository import (
    PreferenceCardRepository,
    card_key_for_row,
    normalise_gold_card_row,
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
