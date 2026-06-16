import json

from domain.clinical_reference_data import CLINICAL_PROCEDURE_PROFILES
from domain.clinical_reference_service import ClinicalReferenceService
from generate_synthetic_data.main_synthetic_generator import generate_single_card
from generate_synthetic_data.main_synthetic_generator import generate_batch
from generate_synthetic_data import mock_data
from generate_synthetic_data import catalogue
from silver_transform.silver_a.silver_a_transformer import SilverTransformer
from silver_transform.silver_b.clinical_enrichment import ClinicalEnrichmentEngine


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


def test_reference_service_exports_normalised_tables():
    service = ClinicalReferenceService()
    validation = service.validate_catalogue()

    assert validation["valid"] is True
    assert validation["procedure_count"] == len(CLINICAL_PROCEDURE_PROFILES)
    assert len(service.procedure_table()) == len(CLINICAL_PROCEDURE_PROFILES)
    assert len(service.instrument_system_table()) > 0
    assert len(service.supply_profile_table()) == len(CLINICAL_PROCEDURE_PROFILES)


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
