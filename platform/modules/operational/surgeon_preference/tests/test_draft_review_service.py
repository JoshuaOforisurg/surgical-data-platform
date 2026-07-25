import json

import pytest

from streamlit_services.draft_review_service import (
    REVIEW_DECISION_PREFIX,
    build_reviewed_draft,
    build_review_decision,
    draft_change_rows,
    draft_display_name,
    load_drafts,
    load_pending_drafts,
    save_review_decision,
    save_reviewed_draft,
    save_review_payload,
)


class FakeStorage:
    def __init__(self, objects: dict[str, str]):
        self.objects = objects

    def list_objects(self, prefix: str) -> list[str]:
        return [key for key in self.objects if key.startswith(prefix)]

    def get_text(self, key: str) -> str:
        return self.objects[key]

    def put_text(self, key: str, text: str, content_type: str = "text/plain") -> None:
        self.objects[key] = text


def _draft(status: str = "pending_review") -> dict:
    return {
        "draft_id": "draft-1",
        "draft_type": "edit",
        "status": status,
        "created_at": "2026-07-16T10:00:00+00:00",
        "surgeon_name": "Mr Test Surgeon",
        "procedure": "Total Knee Replacement",
        "procedure_id": "ORTH_KNEE_001",
        "original": {"equipment": "Tourniquet", "sutures": "Vicryl"},
        "proposed": {"equipment": "Tourniquet and image intensifier", "sutures": "Vicryl"},
        "source_gold_key": "gold/operational/latest/gold_operational_preference_cards.csv",
    }


def test_load_pending_drafts_returns_only_reviewable_json_objects():
    storage = FakeStorage(
        {
            "gold/operational/drafts/002.json": json.dumps(_draft("approved")),
            "gold/operational/drafts/003.json": json.dumps(_draft()),
            "gold/operational/drafts/bad.json": "{not-json",
            "gold/operational/other/001.json": json.dumps(_draft()),
        }
    )

    drafts = load_pending_drafts(storage, "gold/operational/drafts")

    assert len(drafts) == 1
    assert drafts[0]["status"] == "pending_review"
    assert drafts[0]["_object_key"] == "gold/operational/drafts/003.json"


def test_draft_display_and_change_rows_are_human_readable():
    draft = _draft()

    assert draft_display_name(draft).startswith("Edit: Mr Test Surgeon - Total Knee Replacement")
    assert draft_display_name(draft).endswith("[draft-1]")
    assert draft_change_rows(draft) == [
        {
            "field": "Equipment",
            "current": "Tourniquet",
            "proposed": "Tourniquet and image intensifier",
        }
    ]


def test_build_review_decision_validates_reviewer_decision_and_status():
    draft = _draft()
    draft["_object_key"] = "gold/operational/drafts/003.json"

    decision = build_review_decision(
        draft=draft,
        reviewer="Theatre Coordinator",
        decision="approved",
        comments="Confirmed with surgeon.",
        reviewer_email="Reviewer@Example.Com",
        reviewer_roles=("reviewer",),
    )

    assert decision["decision"] == "approved"
    assert decision["reviewer"] == "Theatre Coordinator"
    assert decision["reviewer_email"] == "reviewer@example.com"
    assert decision["reviewer_roles"] == ["reviewer"]
    assert decision["draft_object_key"] == "gold/operational/drafts/003.json"

    with pytest.raises(ValueError, match="Reviewer name is required"):
        build_review_decision(draft, "", "approved")

    with pytest.raises(ValueError, match="Invalid review decision"):
        build_review_decision(draft, "Reviewer", "publish_now")

    with pytest.raises(ValueError, match="Only pending_review drafts"):
        build_review_decision(_draft("approved"), "Reviewer", "approved")


def test_save_review_decision_writes_an_audit_object():
    draft = _draft()
    draft["_object_key"] = "gold/operational/drafts/003.json"
    storage = FakeStorage({})

    key = save_review_decision(
        storage=storage,
        draft=draft,
        reviewer="Theatre Coordinator",
        decision="needs_changes",
        comments="Add implant tray size.",
        reviewer_email="reviewer@example.com",
        reviewer_roles=("reviewer",),
    )

    assert key.startswith(f"{REVIEW_DECISION_PREFIX}/")
    saved = json.loads(storage.objects[key])
    assert saved["decision"] == "needs_changes"
    assert saved["reviewer_email"] == "reviewer@example.com"
    assert saved["reviewer_roles"] == ["reviewer"]
    assert saved["comments"] == "Add implant tray size."


def test_save_review_payload_preserves_existing_review_id():
    storage = FakeStorage({})
    review = {
        "review_id": "fixed-review-id",
        "decision": "approved",
        "reviewer": "Theatre Coordinator",
    }

    key = save_review_payload(storage, review)

    assert key.startswith(f"{REVIEW_DECISION_PREFIX}/")
    assert key.endswith("_fixed-review-id.json")
    assert json.loads(storage.objects[key]) == review


def test_reviewed_draft_status_maps_review_decision_without_mutating_original():
    draft = _draft()
    draft["_object_key"] = "gold/operational/drafts/003.json"
    review = build_review_decision(
        draft=draft,
        reviewer="Theatre Coordinator",
        decision="approved",
        comments="Ready for publishing control.",
        reviewer_email="reviewer@example.com",
        reviewer_roles=("reviewer",),
    )

    updated = build_reviewed_draft(draft, review, "gold/operational/draft_reviews/review.json")

    assert draft["status"] == "pending_review"
    assert updated["status"] == "approved_pending_publish"
    assert updated["review_decision"] == "approved"
    assert updated["review_id"] == review["review_id"]
    assert updated["review_object_key"] == "gold/operational/draft_reviews/review.json"
    assert updated["review_comments"] == "Ready for publishing control."
    assert "_object_key" not in updated


def test_save_reviewed_draft_overwrites_original_draft_and_removes_from_pending_queue():
    draft_key = "gold/operational/drafts/003.json"
    draft = _draft()
    draft["_object_key"] = draft_key
    storage = FakeStorage({draft_key: json.dumps(_draft())})
    review = build_review_decision(
        draft=draft,
        reviewer="Theatre Coordinator",
        decision="needs_changes",
        comments="Clarify implant tray.",
        reviewer_email="reviewer@example.com",
        reviewer_roles=("reviewer",),
    )

    updated = save_reviewed_draft(
        storage,
        draft,
        review,
        "gold/operational/draft_reviews/review.json",
    )

    assert updated["status"] == "changes_requested"
    assert json.loads(storage.objects[draft_key])["status"] == "changes_requested"
    assert load_pending_drafts(storage, "gold/operational/drafts") == []
    assert load_drafts(storage, "gold/operational/drafts")[0]["review_decision"] == "needs_changes"
