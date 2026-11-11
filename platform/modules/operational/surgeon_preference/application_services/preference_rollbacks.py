from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from bronze_Ingestion.catalog import BronzeCatalogRepository
from config.settings import PostgresSettings
from streamlit_renderers.preference_card import current_preference_rows
from streamlit_services.access_control import ADMIN_ROLE, AppUser
from streamlit_services.preference_card_repository import (
    PreferenceCardRepository,
    current_card_rows_to_dataframe,
)
from streamlit_services.publishing_service import save_publish_event, save_published_gold
from streamlit_services.user_registry_service import require_active_membership_role


@dataclass(frozen=True)
class PreferenceRollbackResult:
    rolled_back: bool
    message: str
    published_gold_key: str | None = None
    publish_event_key: str | None = None
    audit_saved: bool = False
    failure_stage: str | None = None
    error: str | None = None


def rollback_preference_card(
    card_id: str,
    source_version_id: str,
    reason: str,
    actor: AppUser | None,
    *,
    organisation_id: str,
    organisation_name: str,
    settings: PostgresSettings | None,
    storage_factory: Callable[[], Any],
    source_gold_key: str,
    repository_factory=PreferenceCardRepository,
    audit_repository_factory=BronzeCatalogRepository,
    rolled_back_at: str | None = None,
) -> PreferenceRollbackResult:
    """Create a new rollback version and archive its tenant-scoped output."""
    if not str(reason or "").strip():
        raise ValueError("Rollback reason is required.")
    membership, access_error = require_active_membership_role(
        settings,
        actor,
        {ADMIN_ROLE},
        organisation_id,
        repository_factory=audit_repository_factory,
    )
    if access_error:
        raise PermissionError(access_error)

    rolled_back_at = rolled_back_at or datetime.now(UTC).isoformat()
    try:
        repository = repository_factory(settings)
        summary = repository.rollback_to_version(
            card_id=card_id,
            source_version_id=source_version_id,
            actor_email=actor.email,
            actor_name=actor.display_name,
            actor_roles=list(membership.get("roles") or []),
            reason=reason,
            source_gold_key=source_gold_key,
            organisation_id=organisation_id,
            rolled_back_at=rolled_back_at,
        )
        if not summary.rolled_back:
            return PreferenceRollbackResult(False, summary.message, failure_stage="operational_rollback")
        current_rows = repository.list_current_cards(organisation_id=organisation_id)
        if not current_rows:
            return PreferenceRollbackResult(
                True,
                summary.message,
                failure_stage="reload_operational_cards",
                error="Rollback succeeded, but current cards could not be reloaded for export.",
            )
        published_gold = current_preference_rows(current_card_rows_to_dataframe(current_rows)).copy()
        rolled_back_card = next(
            (row for row in current_rows if str(row.get("card_id")) == str(card_id)),
            {},
        )
    except Exception as exc:
        return PreferenceRollbackResult(
            False, "Operational rollback failed.", failure_stage="operational_rollback", error=str(exc)
        )

    event = {
        "publish_id": str(uuid.uuid4()),
        "event_type": "preference_card_rollback_published",
        "organisation_id": organisation_id,
        "organisation_name": organisation_name,
        "publisher": actor.display_name,
        "publisher_email": actor.email,
        "publisher_roles": list(membership.get("roles") or []),
        "published_at": rolled_back_at,
        "latest_gold_key": source_gold_key,
        "row_count": len(published_gold),
        "rollback_reason": reason.strip(),
        "card_id": summary.card_id,
        "rollback_version_id": summary.rollback_version_id,
        "source_version_id": summary.source_version_id,
        "from_version_number": summary.from_version_number,
        "to_version_number": summary.to_version_number,
        "surgeon_name": rolled_back_card.get("surgeon_name"),
        "procedure": rolled_back_card.get("procedure_name"),
    }
    try:
        storage = storage_factory()
        gold_key = save_published_gold(
            storage,
            published_gold,
            event["publish_id"],
            source_gold_key,
            organisation_id=organisation_id,
        )
        event["published_gold_key"] = gold_key
        event_key = save_publish_event(storage, event)
    except Exception as exc:
        return PreferenceRollbackResult(
            True, summary.message, failure_stage="archive_rollback", error=str(exc)
        )

    try:
        audit_repository = audit_repository_factory(settings)
        audit_repository.initialise()
        audit_repository.record_publish_event(event, event_key)
    except Exception as exc:
        return PreferenceRollbackResult(
            True, summary.message, gold_key, event_key,
            audit_saved=False, failure_stage="rollback_audit", error=str(exc),
        )

    return PreferenceRollbackResult(
        True, summary.message, gold_key, event_key, audit_saved=True
    )
