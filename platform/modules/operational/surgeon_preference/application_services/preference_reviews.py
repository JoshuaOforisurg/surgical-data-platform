from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from bronze_Ingestion.catalog import BronzeCatalogRepository
from config.settings import PostgresSettings
from streamlit_services.access_control import ADMIN_ROLE, REVIEWER_ROLE, AppUser
from streamlit_services.draft_review_service import (
    build_review_decision,
    save_review_payload,
    save_reviewed_draft,
)
from streamlit_services.user_registry_service import require_active_membership_role


@dataclass(frozen=True)
class DraftReviewResult:
    review: dict[str, Any]
    review_object_key: str
    updated_draft: dict[str, Any]
    audit_saved: bool
    audit_error: str | None = None


def submit_preference_review(
    draft: dict[str, Any],
    reviewer: AppUser | None,
    decision: str,
    comments: str,
    *,
    organisation_id: str,
    organisation_name: str,
    settings: PostgresSettings | None,
    storage_factory: Callable[[], Any],
    repository_factory=BronzeCatalogRepository,
) -> DraftReviewResult:
    """Apply a reviewed decision through an application-layer use case."""
    membership, access_error = require_active_membership_role(
        settings,
        reviewer,
        {REVIEWER_ROLE, ADMIN_ROLE},
        organisation_id,
        repository_factory=repository_factory,
    )
    if access_error:
        raise PermissionError(access_error)

    review = build_review_decision(
        draft=draft,
        reviewer=reviewer.display_name,
        decision=decision,
        comments=comments,
        reviewer_email=reviewer.email,
        reviewer_roles=tuple(membership.get("roles") or []),
        organisation_id=organisation_id,
        organisation_name=organisation_name,
    )
    storage = storage_factory()
    review_key = save_review_payload(storage, review)
    updated_draft = save_reviewed_draft(storage, draft, review, review_key)

    try:
        repository = repository_factory(settings)
        repository.initialise()
        repository.record_draft_review_decision(review, review_key)
    except Exception as exc:
        return DraftReviewResult(
            review=review,
            review_object_key=review_key,
            updated_draft=updated_draft,
            audit_saved=False,
            audit_error=str(exc),
        )

    return DraftReviewResult(review, review_key, updated_draft, audit_saved=True)
