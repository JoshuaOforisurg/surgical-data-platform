from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FHIRPreferenceEvent(BaseModel):
    """
    Internal event produced from EHR/FHIR messages.

    This is deliberately smaller than a preference card. FHIR tells us what is
    happening clinically; the existing reference catalogue decides what the
    theatre team needs for that procedure.
    """

    event_type: str = "procedure_scheduled"
    source_system: str = "ehr_fhir"
    source_message_id: Optional[str] = None
    patient_ref: Optional[str] = None
    encounter_ref: Optional[str] = None
    appointment_ref: Optional[str] = None
    surgeon_ref: Optional[str] = None
    surgeon_name: Optional[str] = None
    procedure_text: Optional[str] = None
    procedure_code: Optional[str] = None
    laterality: Optional[str] = None
    scheduled_start: Optional[datetime | str] = None
    raw_fhir_resource_refs: List[str] = Field(default_factory=list)
    raw_fhir_payload: Dict[str, Any] = Field(default_factory=dict)


class FHIRPreferenceEventAdapter:
    """
    Maps a small FHIR R4-style Bundle into the pipeline's internal event shape.

    The adapter currently focuses on the first learning target:
    ServiceRequest + Appointment + Practitioner -> procedure_scheduled event.
    """

    def from_bundle(self, bundle: Dict[str, Any]) -> FHIRPreferenceEvent:
        resources = self._bundle_resources(bundle)
        service_request = self._first_resource(resources, "ServiceRequest")
        appointment = self._first_resource(resources, "Appointment")
        practitioner = self._first_resource(resources, "Practitioner")

        if not service_request:
            raise ValueError("FHIR bundle does not contain a ServiceRequest resource.")

        code = service_request.get("code") or {}
        coding = self._first_coding(code)
        patient_ref = self._reference(service_request.get("subject"))
        encounter_ref = self._reference(service_request.get("encounter"))
        appointment_ref = self._resource_ref(appointment)
        surgeon_ref = self._performer_ref(service_request) or self._resource_ref(practitioner)

        return FHIRPreferenceEvent(
            source_message_id=self._resource_ref(service_request),
            patient_ref=patient_ref,
            encounter_ref=encounter_ref,
            appointment_ref=appointment_ref,
            surgeon_ref=surgeon_ref,
            surgeon_name=self._practitioner_name(practitioner),
            procedure_text=code.get("text") or coding.get("display"),
            procedure_code=coding.get("code"),
            laterality=self._laterality(service_request),
            scheduled_start=self._appointment_start(appointment),
            raw_fhir_resource_refs=[
                ref
                for ref in [
                    self._resource_ref(service_request),
                    appointment_ref,
                    self._resource_ref(practitioner),
                ]
                if ref
            ],
            raw_fhir_payload=bundle,
        )

    def _bundle_resources(self, bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
        if bundle.get("resourceType") != "Bundle":
            return [bundle] if isinstance(bundle, dict) else []
        return [
            entry.get("resource")
            for entry in bundle.get("entry", [])
            if isinstance(entry.get("resource"), dict)
        ]

    def _first_resource(
        self,
        resources: List[Dict[str, Any]],
        resource_type: str,
    ) -> Optional[Dict[str, Any]]:
        return next(
            (
                resource
                for resource in resources
                if resource.get("resourceType") == resource_type
            ),
            None,
        )

    def _first_coding(self, codeable_concept: Dict[str, Any]) -> Dict[str, Any]:
        coding = codeable_concept.get("coding") or []
        return coding[0] if coding and isinstance(coding[0], dict) else {}

    def _reference(self, reference: Any) -> Optional[str]:
        if isinstance(reference, str):
            return reference
        if isinstance(reference, dict):
            return reference.get("reference")
        return None

    def _resource_ref(self, resource: Optional[Dict[str, Any]]) -> Optional[str]:
        if not resource:
            return None
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")
        if not resource_type or not resource_id:
            return None
        return f"{resource_type}/{resource_id}"

    def _performer_ref(self, service_request: Dict[str, Any]) -> Optional[str]:
        performers = service_request.get("performer") or []
        for performer in performers:
            ref = self._reference(performer)
            if ref:
                return ref
        return None

    def _appointment_start(self, appointment: Optional[Dict[str, Any]]) -> Optional[str]:
        if not appointment:
            return None
        return appointment.get("start")

    def _practitioner_name(self, practitioner: Optional[Dict[str, Any]]) -> Optional[str]:
        if not practitioner:
            return None
        names = practitioner.get("name") or []
        if not names:
            return None
        name = names[0]
        prefix = " ".join(name.get("prefix") or [])
        given = " ".join(name.get("given") or [])
        family = name.get("family") or ""
        return " ".join(part for part in [prefix, given, family] if part).strip() or None

    def _laterality(self, service_request: Dict[str, Any]) -> Optional[str]:
        body_sites = service_request.get("bodySite") or []
        for body_site in body_sites:
            text = str(body_site.get("text") or "").lower()
            if "left" in text:
                return "left"
            if "right" in text:
                return "right"
        return None
