"""Versioned transport contracts for future HTTP/API adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PreferenceCardSearchRequest(ContractModel):
    surgeon_query: str = Field(default="", max_length=160)
    procedure_query: str = Field(default="", max_length=200)


class PreferenceCardSearchResponse(ContractModel):
    cards: list[dict[str, Any]]
    count: int = Field(ge=0)
    source: Literal["Operational database", "Gold snapshot fallback", "Unavailable"]
    source_layer: Literal["Postgres", "Gold", "None"]
    fallback_used: bool
    message: str

    @field_validator("count")
    @classmethod
    def count_matches_cards(cls, value: int, info):
        cards = info.data.get("cards")
        if cards is not None and value != len(cards):
            raise ValueError("count must equal the number of cards")
        return value


def search_response_from_query(cards, query_result: dict[str, Any]) -> PreferenceCardSearchResponse:
    frame = cards.astype(object).where(cards.notna(), None)
    return PreferenceCardSearchResponse(
        cards=frame.to_dict(orient="records"),
        count=len(frame),
        source=query_result["source"],
        source_layer=query_result["source_layer"],
        fallback_used=bool(query_result["fallback_used"]),
        message=query_result["message"],
    )


class PreferenceDraftSubmissionRequest(ContractModel):
    draft_id: str = Field(min_length=1, max_length=128)
    draft_type: Literal["create", "edit"]
    original: dict[str, Any] = Field(default_factory=dict)
    proposed: dict[str, Any]


class PreferenceReviewRequest(ContractModel):
    decision: Literal["approved", "needs_changes", "rejected"]
    comments: str = Field(default="", max_length=4000)


class PreferenceRollbackRequest(ContractModel):
    card_id: str = Field(min_length=1, max_length=128)
    source_version_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=2000)
