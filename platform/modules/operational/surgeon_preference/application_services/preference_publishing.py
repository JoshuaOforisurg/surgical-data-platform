from __future__ import annotations

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
from streamlit_services.publishing_service import (
    APPROVED_DRAFT_STATUS,
    build_publish_event,
    mark_draft_published,
    save_publish_event,
    save_published_gold,
)
from streamlit_services.user_registry_service import require_active_membership_role


@dataclass(frozen=True)
class PreferencePublishResult:
    operational_published: bool
    operational_message: str
    published_gold_key: str | None = None
    publish_event_key: str | None = None
    updated_draft: dict[str, Any] | None = None
    audit_saved: bool = False
    failure_stage: str | None = None
    error: str | None = None


def publish_preference_draft(
    draft: dict[str, Any],
    publisher: AppUser | None,
    *,
    organisation_id: str,
    organisation_name: str,
    settings: PostgresSettings | None,
    storage_factory: Callable[[], Any],
    editable_fields: list[str],
    source_gold_key: str,
    repository_factory=PreferenceCardRepository,
    audit_repository_factory=BronzeCatalogRepository,
    published_at: str | None = None,
) -> PreferencePublishResult:
    """Publish an approved card and archive its tenant-scoped output."""
    if draft.get("status") != APPROVED_DRAFT_STATUS:
        raise ValueError("Only approved_pending_publish drafts can be published.")
    draft_org = str(draft.get("organisation_id") or "default").strip() or "default"
    if draft_org != str(organisation_id).strip():
        raise ValueError("Draft organisation does not match publisher organisation.")
    if not draft.get("_object_key"):
        raise ValueError("Draft object key is required before publishing.")

    membership, access_error = require_active_membership_role(
        settings,
        publisher,
        {ADMIN_ROLE},
        organisation_id,
        repository_factory=audit_repository_factory,
    )
    if access_error:
        raise PermissionError(access_error)

    published_at = published_at or datetime.now(UTC).isoformat()
    try:
        repository = repository_factory(settings)
        summary = repository.publish_approved_draft(
            draft=draft,
            publisher=publisher.email,
            editable_fields=editable_fields,
            source_gold_key=source_gold_key,
            organisation_id=organisation_id,
            published_at=published_at,
        )
        if not summary.published:
            return PreferencePublishResult(
                False, summary.message, failure_stage="operational_publish", error=summary.message
            )
        current_rows = repository.list_current_cards(organisation_id=organisation_id)
        if not current_rows:
            return PreferencePublishResult(
                True,
                summary.message,
                failure_stage="reload_operational_cards",
                error="Operational publish succeeded, but current cards could not be reloaded.",
            )
        published_gold = current_preference_rows(current_card_rows_to_dataframe(current_rows)).copy()
    except Exception as exc:
        return PreferencePublishResult(
            False, "Operational preference publish failed.",
            failure_stage="operational_publish", error=str(exc),
        )

    try:
        storage = storage_factory()
        publish_event = build_publish_event(
            draft=draft,
            publisher=publisher.display_name,
            publisher_email=publisher.email,
            publisher_roles=tuple(membership.get("roles") or []),
            published_gold_key="",
            latest_gold_key=source_gold_key,
            row_count=len(published_gold),
            published_at=published_at,
            organisation_id=organisation_id,
            organisation_name=organisation_name,
        )
        publish_event.update(
            {
                "card_id": summary.card_id,
                "version_id": summary.version_id,
                "version_number": summary.version_number,
            }
        )
        gold_key = save_published_gold(
            storage, published_gold, publish_event["publish_id"], source_gold_key
        )
        publish_event["published_gold_key"] = gold_key
        event_key = save_publish_event(storage, publish_event)
        updated_draft = mark_draft_published(storage, draft, publish_event, event_key)
    except Exception as exc:
        return PreferencePublishResult(
            True, summary.message, failure_stage="archive_publish", error=str(exc)
        )

    try:
        audit_repository = audit_repository_factory(settings)
        audit_repository.initialise()
        audit_repository.record_publish_event(publish_event, event_key)
    except Exception as exc:
        return PreferencePublishResult(
            True, summary.message, gold_key, event_key, updated_draft,
            audit_saved=False, failure_stage="publish_audit", error=str(exc),
        )

    return PreferencePublishResult(
        True, summary.message, gold_key, event_key, updated_draft, audit_saved=True
    )
