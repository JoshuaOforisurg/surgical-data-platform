import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from streamlit_renderers.preference_card import current_preference_rows


PUBLISH_EVENT_PREFIX = "gold/operational/publish_events"
PUBLISHED_GOLD_PREFIX = "gold/operational/published"
APPROVED_DRAFT_STATUS = "approved_pending_publish"
PUBLISHED_DRAFT_STATUS = "published"


def load_publishable_drafts(storage, draft_prefix: str, limit: int = 100) -> list[dict[str, Any]]:
    from streamlit_services.draft_review_service import load_drafts

    return [
        draft
        for draft in load_drafts(storage, draft_prefix, limit)
        if draft.get("status") == APPROVED_DRAFT_STATUS
    ]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _coerce_version(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 1


def _matching_mask(df: pd.DataFrame, draft: dict[str, Any]) -> pd.Series:
    mask = pd.Series(True, index=df.index)

    if draft.get("surgeon_id") and "surgeon_id" in df.columns:
        mask &= df["surgeon_id"].astype(str) == str(draft["surgeon_id"])
    elif draft.get("surgeon_name") and "surgeon_name" in df.columns:
        mask &= df["surgeon_name"].astype(str) == str(draft["surgeon_name"])

    if draft.get("procedure_id") and "procedure_id" in df.columns:
        mask &= df["procedure_id"].astype(str) == str(draft["procedure_id"])
    elif draft.get("procedure") and "procedure" in df.columns:
        mask &= df["procedure"].astype(str) == str(draft["procedure"])

    return mask


def apply_approved_draft_to_gold(
    current_gold: pd.DataFrame,
    draft: dict[str, Any],
    publisher: str,
    editable_fields: list[str],
    published_at: str | None = None,
) -> pd.DataFrame:
    if draft.get("status") != APPROVED_DRAFT_STATUS:
        raise ValueError("Only approved_pending_publish drafts can be published.")

    if current_gold is None or current_gold.empty:
        raise ValueError("Current Gold data is required before publishing a draft.")

    published_at = published_at or _now_iso()
    proposed = draft.get("proposed") or {}
    working = current_preference_rows(current_gold).copy().reset_index(drop=True)

    if draft.get("draft_type") == "create":
        new_row = {column: "" for column in working.columns}
        new_row.update(
            {
                "surgeon_id": draft.get("surgeon_id", ""),
                "surgeon_name": draft.get("surgeon_name", ""),
                "specialty": draft.get("specialty", ""),
                "subspecialty": draft.get("subspecialty", ""),
                "procedure": draft.get("procedure", ""),
                "procedure_id": draft.get("procedure_id", ""),
                "preference_card_version": 1,
                "preference_card_version_label": "v1",
                "version_number": 1,
                "version_updated_by": publisher,
                "version_updated_at": published_at,
                "is_current": True,
            }
        )
        for field in editable_fields:
            if field in working.columns and field in proposed:
                new_row[field] = proposed[field]
        return pd.concat([working, pd.DataFrame([new_row])], ignore_index=True)

    mask = _matching_mask(working, draft)
    matches = working[mask]
    if matches.empty:
        raise ValueError("Approved edit draft does not match a current Gold preference card.")

    index = matches.index[0]
    current_version = _coerce_version(
        working.at[index, "preference_card_version"]
        if "preference_card_version" in working.columns
        else working.at[index, "version_number"]
        if "version_number" in working.columns
        else 1
    )
    next_version = current_version + 1

    for field in editable_fields:
        if field in working.columns and field in proposed:
            working.at[index, field] = proposed[field]

    version_fields = {
        "preference_card_version": next_version,
        "preference_card_version_label": f"v{next_version}",
        "version_number": next_version,
        "version_updated_by": publisher,
        "version_updated_at": published_at,
        "is_current": True,
    }
    for field, value in version_fields.items():
        if field in working.columns:
            working.at[index, field] = value

    return working


def build_publish_event(
    draft: dict[str, Any],
    publisher: str,
    publisher_email: str,
    publisher_roles: tuple[str, ...],
    published_gold_key: str,
    latest_gold_key: str,
    row_count: int,
    published_at: str | None = None,
) -> dict[str, Any]:
    published_at = published_at or _now_iso()
    return {
        "publish_id": str(uuid.uuid4()),
        "draft_id": draft.get("draft_id"),
        "draft_object_key": draft.get("_object_key"),
        "review_id": draft.get("review_id"),
        "review_object_key": draft.get("review_object_key"),
        "draft_type": draft.get("draft_type"),
        "publisher": publisher.strip(),
        "publisher_email": publisher_email.strip().lower(),
        "publisher_roles": list(publisher_roles),
        "published_at": published_at,
        "published_gold_key": published_gold_key,
        "latest_gold_key": latest_gold_key,
        "row_count": row_count,
        "surgeon_id": draft.get("surgeon_id"),
        "surgeon_name": draft.get("surgeon_name"),
        "procedure": draft.get("procedure"),
        "procedure_id": draft.get("procedure_id"),
    }


def save_publish_event(storage, publish_event: dict[str, Any]) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    key = f"{PUBLISH_EVENT_PREFIX}/{timestamp}_{publish_event['publish_id']}.json"
    storage.put_text(key, json.dumps(publish_event, indent=2), "application/json")
    return key


def save_published_gold(
    storage,
    published_gold: pd.DataFrame,
    publish_id: str,
    latest_gold_key: str,
) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    published_key = f"{PUBLISHED_GOLD_PREFIX}/{timestamp}_{publish_id}/gold_operational_preference_cards.csv"
    csv_text = published_gold.to_csv(index=False)
    storage.put_text(published_key, csv_text, "text/csv")
    storage.put_text(latest_gold_key, csv_text, "text/csv")
    return published_key


def mark_draft_published(
    storage,
    draft: dict[str, Any],
    publish_event: dict[str, Any],
    publish_event_key: str,
) -> dict[str, Any]:
    draft_object_key = draft.get("_object_key")
    if not draft_object_key:
        raise ValueError("Draft object key is required before a draft can be published.")

    updated = {key: value for key, value in draft.items() if key != "_object_key"}
    updated["status"] = PUBLISHED_DRAFT_STATUS
    updated["publish_id"] = publish_event["publish_id"]
    updated["publish_event_key"] = publish_event_key
    updated["published_gold_key"] = publish_event["published_gold_key"]
    updated["latest_gold_key"] = publish_event["latest_gold_key"]
    updated["published_at"] = publish_event["published_at"]
    updated["publisher"] = publish_event["publisher"]
    updated["publisher_email"] = publish_event["publisher_email"]
    storage.put_text(draft_object_key, json.dumps(updated, indent=2), "application/json")
    return updated
