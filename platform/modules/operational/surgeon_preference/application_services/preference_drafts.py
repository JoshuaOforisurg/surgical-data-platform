from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from bronze_Ingestion.catalog import BronzeCatalogRepository
from config.settings import PostgresSettings
from streamlit_services.access_control import ADMIN_ROLE, EDITOR_ROLE, REVIEWER_ROLE, AppUser
from streamlit_services.user_registry_service import require_active_membership_role


DRAFT_PREFIX = "gold/operational/drafts"


@dataclass(frozen=True)
class DraftSubmissionResult:
    draft: dict[str, Any]
    object_key: str
    audit_saved: bool
    audit_error: str | None = None


def submit_preference_draft(
    payload: dict[str, Any],
    submitter: AppUser | None,
    *,
    settings: PostgresSettings | None,
    storage_factory: Callable[[], Any],
    repository_factory=BronzeCatalogRepository,
    submitted_at: str | None = None,
) -> DraftSubmissionResult:
    """Submit a tenant-scoped draft without depending on a UI framework."""
    _, access_error = require_active_membership_role(
        settings,
        submitter,
        {EDITOR_ROLE, REVIEWER_ROLE, ADMIN_ROLE},
        repository_factory=repository_factory,
    )
    if access_error:
        raise PermissionError(access_error)

    storage = storage_factory()

    submitted_at = submitted_at or datetime.now(UTC).isoformat()
    draft = {
        **payload,
        "submitted_by": submitter.display_name,
        "submitter_email": submitter.email,
        "submitter_roles": list(submitter.roles),
        "submitter_status": submitter.status,
        "organisation_id": submitter.organisation_id,
        "organisation_name": submitter.organisation_name,
        "created_at": payload.get("created_at") or submitted_at,
    }
    stamp = datetime.fromisoformat(submitted_at.replace("Z", "+00:00")).strftime("%Y%m%d_%H%M%S")
    object_key = f"{DRAFT_PREFIX}/{stamp}_{draft['draft_id']}.json"
    storage.put_text(object_key, json.dumps(draft, indent=2), "application/json")

    try:
        repository = repository_factory(settings)
        repository.initialise()
        repository.record_draft_submission(draft, object_key)
    except Exception as exc:
        return DraftSubmissionResult(
            draft=draft,
            object_key=object_key,
            audit_saved=False,
            audit_error=str(exc),
        )

    return DraftSubmissionResult(draft, object_key, audit_saved=True)
