import json

from domain.clinical_reference_data import CLINICAL_PROCEDURE_PROFILES
from domain.clinical_reference_service import ClinicalReferenceService
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
