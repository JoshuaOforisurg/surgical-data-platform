import pytest
from pydantic import ValidationError

from application_services.contracts import (
    PreferenceCardSearchRequest,
    PreferenceCardSearchResponse,
    PreferenceDraftSubmissionRequest,
    PreferenceReviewRequest,
    PreferenceRollbackRequest,
    search_response_from_query,
)


def test_search_contract_has_stable_serializable_shape():
    request = PreferenceCardSearchRequest(surgeon_query=" Dr A ", procedure_query="hip")
    response = PreferenceCardSearchResponse(
        cards=[{"surgeon_name": "Dr A", "procedure": "Hip"}],
        count=1,
        source="Operational database",
        source_layer="Postgres",
        fallback_used=False,
        message="Current cards loaded.",
    )

    assert request.model_dump() == {"surgeon_query": "Dr A", "procedure_query": "hip"}
    assert response.model_dump(mode="json")["count"] == 1


def test_response_rejects_inconsistent_count_and_unknown_fields():
    with pytest.raises(ValidationError, match="count must equal"):
        PreferenceCardSearchResponse(
            cards=[{}], count=2, source="Unavailable", source_layer="None",
            fallback_used=True, message="No data",
        )
    with pytest.raises(ValidationError):
        PreferenceCardSearchRequest(unbounded_query="anything")


def test_application_response_builder_converts_dataframe_to_wire_contract():
    import pandas as pd

    response = search_response_from_query(
        pd.DataFrame([{"surgeon_name": "Dr A", "procedure": "Hip", "optional": float("nan")}]),
        {
            "source": "Operational database",
            "source_layer": "Postgres",
            "fallback_used": False,
            "message": "Current cards loaded.",
        },
    )

    assert response.count == 1
    assert response.cards[0]["optional"] is None


def test_workflow_contracts_validate_decisions_and_required_rollback_reason():
    assert PreferenceDraftSubmissionRequest(
        draft_id="draft-1", draft_type="create", proposed={"procedure": "Hip"}
    ).draft_type == "create"
    assert PreferenceReviewRequest(decision="approved").decision == "approved"
    with pytest.raises(ValidationError):
        PreferenceReviewRequest(decision="publish")
    with pytest.raises(ValidationError):
        PreferenceRollbackRequest(card_id="card-1", source_version_id="v1", reason=" ")
