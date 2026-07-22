import json
import uuid
from datetime import UTC, datetime
from typing import Any


REVIEW_DECISION_PREFIX = "gold/operational/draft_reviews"
VALID_REVIEW_DECISIONS = {"approved", "needs_changes", "rejected"}


def load_pending_drafts(storage, draft_prefix: str, limit: int = 50) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    keys = sorted(storage.list_objects(draft_prefix), reverse=True)

    for key in keys[:limit]:
        try:
            draft = json.loads(storage.get_text(key))
        except (json.JSONDecodeError, OSError, ValueError):
            continue

        if draft.get("status") != "pending_review":
            continue

        draft["_object_key"] = key
        drafts.append(draft)

    return drafts


def draft_display_name(draft: dict[str, Any]) -> str:
    draft_type = str(draft.get("draft_type") or "draft").replace("_", " ").title()
    surgeon = draft.get("surgeon_name") or "Unknown surgeon"
    procedure = draft.get("procedure") or "Unknown procedure"
    created_at = draft.get("created_at") or "unknown date"
    draft_id = str(draft.get("draft_id") or draft.get("_object_key") or "unknown-draft")
    return f"{draft_type}: {surgeon} - {procedure} ({created_at}) [{draft_id}]"


def draft_change_rows(draft: dict[str, Any]) -> list[dict[str, str]]:
    original = draft.get("original") or {}
    proposed = draft.get("proposed") or {}
    fields = sorted(set(original) | set(proposed))

    rows = []
    for field in fields:
        current_value = original.get(field, "")
        proposed_value = proposed.get(field, "")
        if current_value == proposed_value:
            continue

        rows.append(
            {
                "field": field.replace("_", " ").title(),
                "current": str(current_value or ""),
                "proposed": str(proposed_value or ""),
            }
        )

    return rows


def build_review_decision(
    draft: dict[str, Any],
    reviewer: str,
    decision: str,
    comments: str = "",
    reviewer_email: str = "",
    reviewer_roles: tuple[str, ...] = (),
) -> dict[str, Any]:
    normalised_decision = decision.strip().lower()
    if normalised_decision not in VALID_REVIEW_DECISIONS:
        raise ValueError(f"Invalid review decision: {decision}")

    if draft.get("status") != "pending_review":
        raise ValueError("Only pending_review drafts can receive a review decision.")

    reviewer_name = reviewer.strip()
    if not reviewer_name:
        raise ValueError("Reviewer name is required.")

    return {
        "review_id": str(uuid.uuid4()),
        "draft_id": draft.get("draft_id"),
        "draft_object_key": draft.get("_object_key"),
        "draft_type": draft.get("draft_type"),
        "decision": normalised_decision,
        "reviewer": reviewer_name,
        "reviewer_email": reviewer_email.strip().lower(),
        "reviewer_roles": list(reviewer_roles),
        "comments": comments.strip(),
        "reviewed_at": datetime.now(UTC).isoformat(),
        "source_gold_key": draft.get("source_gold_key"),
        "surgeon_id": draft.get("surgeon_id"),
        "surgeon_name": draft.get("surgeon_name"),
        "procedure": draft.get("procedure"),
        "procedure_id": draft.get("procedure_id"),
    }


def save_review_decision(
    storage,
    draft: dict[str, Any],
    reviewer: str,
    decision: str,
    comments: str = "",
    reviewer_email: str = "",
    reviewer_roles: tuple[str, ...] = (),
) -> str:
    review = build_review_decision(
        draft=draft,
        reviewer=reviewer,
        decision=decision,
        comments=comments,
        reviewer_email=reviewer_email,
        reviewer_roles=reviewer_roles,
    )
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    key = f"{REVIEW_DECISION_PREFIX}/{timestamp}_{review['review_id']}.json"
    storage.put_text(key, json.dumps(review, indent=2), "application/json")
    return key
