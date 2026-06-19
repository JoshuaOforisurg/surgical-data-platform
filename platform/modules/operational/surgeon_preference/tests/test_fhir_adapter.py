import json
from pathlib import Path

from adapters.fhir_adapter import FHIRPreferenceEventAdapter


def test_fhir_bundle_maps_to_internal_preference_event():
    bundle_path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "fhir"
        / "procedure_scheduled_bundle.json"
    )
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    event = FHIRPreferenceEventAdapter().from_bundle(bundle)

    assert event.event_type == "procedure_scheduled"
    assert event.source_system == "ehr_fhir"
    assert event.source_message_id == "ServiceRequest/service-request-001"
    assert event.patient_ref == "Patient/example-patient"
    assert event.appointment_ref == "Appointment/appointment-001"
    assert event.surgeon_ref == "Practitioner/surgeon-001"
    assert event.surgeon_name == "Mr Test Surgeon"
    assert event.procedure_text == "Total Knee Replacement"
    assert event.procedure_code == "W40.1"
    assert event.laterality == "left"
    assert event.scheduled_start == "2026-07-01T09:00:00Z"
    assert "ServiceRequest/service-request-001" in event.raw_fhir_resource_refs
