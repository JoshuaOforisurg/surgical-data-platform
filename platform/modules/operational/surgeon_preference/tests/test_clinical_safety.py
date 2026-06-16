import json

import pandas as pd

from domain.clinical_reference_data import CLINICAL_PROCEDURE_PROFILES
from domain.clinical_reference_service import ClinicalReferenceService
from generate_synthetic_data.main_synthetic_generator import generate_single_card
from generate_synthetic_data.main_synthetic_generator import generate_batch
from generate_synthetic_data import mock_data
from generate_synthetic_data import catalogue
from gold_cleaned.operational_preference_card import OperationalPreferenceGoldBuilder
from silver_transform.silver_a.silver_a_transformer import SilverTransformer
from silver_transform.silver_b.clinical_enrichment import ClinicalEnrichmentEngine
from streamlit_renderers.preference_card import build_preference_card, current_preference_rows


def _items(names):
    return json.dumps([{"name": name, "quantity": 1} for name in names])


def test_each_procedure_uses_configured_system():
    engine = ClinicalEnrichmentEngine()

    for procedure_id, profile in CLINICAL_PROCEDURE_PROFILES.items():
        record = {
            "procedure_name": profile["name"],
            "instruments": _items(profile.get("expected_instruments", [])),
            "implants": _items(profile.get("expected_implants", [])),
            "equipment": _items(profile.get("expected_equipment", [])),
        }

        enriched = engine.enrich(record)

        assert enriched["clinical_resolution"]["procedure_id"] == procedure_id
        assert enriched["clinical_resolution"]["system_id"] == profile["instrument_systems"][0]


def test_observed_wrong_system_requires_review():
    engine = ClinicalEnrichmentEngine()
    hip = CLINICAL_PROCEDURE_PROFILES["ORTH_JOINT_HIP_001"]

    enriched = engine.enrich(
        {
            "procedure_name": hip["name"],
            "instrument_system": "JOURNEY II BCS Total Knee Instrumentation",
            "instruments": _items(hip["expected_instruments"]),
            "implants": _items(hip["expected_implants"]),
            "equipment": _items(hip["expected_equipment"]),
        }
    )

    assert enriched["clinical_resolution"]["system_id"] == "SYS_HIP_R3_001"
    assert "OBSERVED_SYSTEM_PROCEDURE_MISMATCH" in enriched["clinical_validation"]["flags"]
    assert enriched["clinical_validation"]["readiness_status"] == "Review required"


def test_messy_special_instructions_are_canonicalised():
    service = ClinicalReferenceService()

    assert (
        service.normalise_instruction("Ensure implant trays arecomplete")
        == "Confirm all implant trays are complete."
    )
    assert (
        service.normalise_instruction("Confirm patent positioning before prepping")
        == "Confirm patient positioning before skin preparation."
    )
    assert (
        service.normalise_instruction("Doublec-heck prosthesis sizes with surgeon")
        == "Confirm prosthesis sizes with the surgeon."
    )


def test_procedure_specific_special_instructions_are_available():
    service = ClinicalReferenceService()

    for procedure_id in CLINICAL_PROCEDURE_PROFILES:
        instructions = service.instructions_for_procedure(procedure_id)

        assert instructions, procedure_id
        assert all(instruction.endswith(".") for instruction in instructions)


def test_special_instruction_normalisation_stays_procedure_specific():
    service = ClinicalReferenceService()
    hip_id = "ORTH_JOINT_HIP_001"

    normalised = service.normalise_instruction_for_procedure(
        "Check tourniquet pressure before cementing",
        hip_id,
    )

    assert normalised in service.instructions_for_procedure(hip_id)
    assert "tourniquet" not in normalised.lower()


def test_reference_service_exports_normalised_tables():
    service = ClinicalReferenceService()
    validation = service.validate_catalogue()

    assert validation["valid"] is True
    assert validation["procedure_count"] == len(CLINICAL_PROCEDURE_PROFILES)
    assert len(service.procedure_table()) == len(CLINICAL_PROCEDURE_PROFILES)
    assert len(service.instrument_system_table()) > 0
    assert len(service.supply_profile_table()) == len(CLINICAL_PROCEDURE_PROFILES)
    assert len(service.operational_metadata_table()) == len(CLINICAL_PROCEDURE_PROFILES)


def test_clinical_catalogue_has_realistic_operational_metadata():
    service = ClinicalReferenceService()

    for row in service.operational_metadata_table():
        assert row.expected_positioning, row.procedure_id
        assert row.expected_anaesthetic, row.procedure_id
        assert row.expected_skin_prep, row.procedure_id
        assert row.theatre_environment, row.procedure_id
        assert row.case_complexity in {"Low", "Moderate", "High"}
        assert row.expected_duration_minutes and row.expected_duration_minutes > 0
        assert row.turnaround_minutes and row.turnaround_minutes > 0
        assert row.critical_checks, row.procedure_id


def test_synthetic_cards_use_procedure_specific_supplies(tmp_path):
    for _ in range(20):
        card = generate_single_card(output_dir=str(tmp_path), messy=False, export=False)
        profile = mock_data.CLINICAL_PREFERENCE_PROFILES[card.procedure.name]

        assert {item.name for item in card.instruments}.issubset(
            {item["name"] for item in profile["instruments"]}
        )
        expected_draping = {
            profile["drape_pack"],
            *profile.get("draping_order", []),
        }

        assert {item.name for item in card.draping}.issubset(expected_draping)
        assert {item.name for item in card.consumables} == set(profile["consumables"])
        assert {item.name for item in card.disposables} == set(profile["disposables"])
        assert {item.name for item in card.sutures} == set(profile["sutures"])
        assert {item.name for item in card.dressings} == set(profile["dressings"])

        if card.implants:
            assert {item.name for item in card.implants}.issubset(set(profile["implants"]))

        procedure_id = ClinicalReferenceService().resolve_procedure(card.procedure.name)
        assert card.special_instructions.notes in ClinicalReferenceService().instructions_for_procedure(
            procedure_id
        )


def test_mock_catalogue_has_complete_frontline_sections():
    for procedure_name, profile in mock_data.CLINICAL_PREFERENCE_PROFILES.items():
        assert profile.get("drape_pack"), procedure_name
        assert profile.get("instruments"), procedure_name
        assert profile.get("equipment"), procedure_name
        assert profile.get("consumables"), procedure_name
        assert profile.get("disposables"), procedure_name
        assert profile.get("sutures"), procedure_name
        assert profile.get("dressings"), procedure_name


def test_legacy_mock_data_facade_matches_modular_catalogue():
    assert mock_data.PROCEDURES is catalogue.PROCEDURES
    assert mock_data.CLINICAL_PREFERENCE_PROFILES is catalogue.CLINICAL_PREFERENCE_PROFILES
    assert mock_data.SPECIAL_INSTRUCTIONS_POOL is catalogue.SPECIAL_INSTRUCTIONS_POOL


def test_synthetic_surgeon_titles_use_uk_consultant_style():
    assert all(
        name.startswith(("Mr ", "Ms ", "Miss ", "Mrs "))
        for name in mock_data.SURGEON_NAMES
    )
    assert not any(name.startswith("Dr ") for name in mock_data.SURGEON_NAMES)


def test_partitioned_generation_writes_structured_files(tmp_path):
    generate_batch(
        n=12,
        output_dir=str(tmp_path),
        messy=False,
        output_mode="partitioned",
        file_formats="json,csv",
    )

    partitioned = tmp_path / "partitioned"
    files = sorted(path.name for path in partitioned.iterdir())

    assert len(files) == 12
    assert any(file.endswith(".json") for file in files)
    assert any(file.endswith(".csv") for file in files)
    assert not (tmp_path / "master_preferences.json").exists()


def test_flat_csv_structural_items_survive_silver_a():
    transformer = SilverTransformer()
    row = transformer.flatten_card(
        {
            "metadata": {},
            "content": {
                "surgeon_name": "Dr Test",
                "procedure_name": "Total Knee Replacement",
                "procedure_codes": "0SRC0JZ",
                "diagnosis_codes": "M17.10",
                "instruments": "JOURNEY II BCS Knee System (x7), Large Orthopaedic Set (x1)",
                "equipment": "Stryker SmartPump Tourniquet System (Req: True)",
                "consumables": "Skin Marker Pen (x1), Suction Tubing (x2)",
                "disposables": "Disposable Saw Blade - Oscillating (x1)",
            },
        }
    )

    assert row["procedure_codes"] == '["0SRC0JZ"]'
    assert "JOURNEY II BCS Knee System" in row["instruments"]
    assert "Skin Marker Pen" in row["consumables"]


def test_gold_builder_publishes_one_current_card_per_surgeon_procedure():
    builder = OperationalPreferenceGoldBuilder()
    base_record = {
        "surgeon_id": "S001",
        "surgeon_name": "Mr Test Surgeon",
        "hospital": "Test Hospital",
        "clinical_resolution": {
            "procedure_id": "ORTH_JOINT_KNEE_001",
            "procedure_name": "Total Knee Replacement",
            "system_name": "JOURNEY II BCS Total Knee Instrumentation",
            "implant_system": "JOURNEY II BCS Total Knee System",
        },
        "instruments": [{"name": "Older Knee Tray", "quantity": 1}],
        "version_number": 1,
        "version_updated_at": "2026-01-01T00:00:00+00:00",
    }
    newer_record = {
        **base_record,
        "instruments": [{"name": "Current Knee Tray", "quantity": 1}],
        "version_number": 3,
        "version_updated_at": "2026-02-01T00:00:00+00:00",
    }

    rows = builder.build([base_record, newer_record])

    assert len(rows) == 1
    assert rows[0]["preference_card_version"] == 3
    assert rows[0]["instrument_set"] == "Current Knee Tray (x1)"
    assert rows[0]["is_current"] is True


def test_streamlit_renderer_uses_latest_card_when_duplicates_exist():
    rows = pd.DataFrame(
        [
            {
                "surgeon_name": "Mr Test Surgeon",
                "procedure": "Total Knee Replacement",
                "procedure_id": "ORTH_JOINT_KNEE_001",
                "instrument_set": "Older Knee Tray",
                "preference_card_version": 1,
                "version_updated_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "surgeon_name": "Mr Test Surgeon",
                "procedure": "Total Knee Replacement",
                "procedure_id": "ORTH_JOINT_KNEE_001",
                "instrument_set": "Current Knee Tray",
                "preference_card_version": 4,
                "version_updated_at": "2026-03-01T00:00:00+00:00",
            },
        ]
    )

    current_rows = current_preference_rows(rows)
    card = build_preference_card(rows, "Mr Test Surgeon", "Total Knee Replacement")

    assert len(current_rows) == 1
    assert len(card["procedures"]) == 1
    assert card["procedures"][0]["instrument_set"] == "Current Knee Tray"
    assert card["procedures"][0]["preference_card_version"] == 4
