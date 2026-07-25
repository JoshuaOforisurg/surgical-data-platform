import json
import uuid
from datetime import UTC, datetime
from typing import Any


REVIEW_DECISION_PREFIX = "gold/operational/draft_reviews"
VALID_REVIEW_DECISIONS = {"approved", "needs_changes", "rejected"}
DRAFT_STATUS_BY_DECISION = {
    "approved": "approved_pending_publish",
    "needs_changes": "changes_requested",
    "rejected": "rejected",
}


def load_drafts(storage, draft_prefix: str, limit: int = 100) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    keys = sorted(storage.list_objects(draft_prefix), reverse=True)

    for key in keys[:limit]:
        try:
            draft = json.loads(storage.get_text(key))
        except (json.JSONDecodeError, OSError, ValueError):
            continue

        draft["_object_key"] = key
        drafts.append(draft)

    return drafts


def load_pending_drafts(storage, draft_prefix: str, limit: int = 50) -> list[dict[str, Any]]:
    return [
        draft
        for draft in load_drafts(storage, draft_prefix, limit)
        if draft.get("status") == "pending_review"
    ]


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
    return save_review_payload(storage, review)


def save_review_payload(storage, review: dict[str, Any]) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    key = f"{REVIEW_DECISION_PREFIX}/{timestamp}_{review['review_id']}.json"
    storage.put_text(key, json.dumps(review, indent=2), "application/json")
    return key


def build_reviewed_draft(
    draft: dict[str, Any],
    review: dict[str, Any],
    review_object_key: str,
) -> dict[str, Any]:
    decision = review.get("decision")
    if decision not in DRAFT_STATUS_BY_DECISION:
        raise ValueError(f"Invalid review decision: {decision}")

    updated = {key: value for key, value in draft.items() if key != "_object_key"}
    updated["status"] = DRAFT_STATUS_BY_DECISION[decision]
    updated["review_decision"] = decision
    updated["review_id"] = review["review_id"]
    updated["review_object_key"] = review_object_key
    updated["reviewed_at"] = review["reviewed_at"]
    updated["reviewer"] = review.get("reviewer")
    updated["reviewer_email"] = review.get("reviewer_email")
    updated["review_comments"] = review.get("comments", "")
    return updated


def save_reviewed_draft(
    storage,
    draft: dict[str, Any],
    review: dict[str, Any],
    review_object_key: str,
) -> dict[str, Any]:
    draft_object_key = draft.get("_object_key")
    if not draft_object_key:
        raise ValueError("Draft object key is required before a draft can be updated.")

    updated = build_reviewed_draft(draft, review, review_object_key)
    storage.put_text(draft_object_key, json.dumps(updated, indent=2), "application/json")
    return updated
