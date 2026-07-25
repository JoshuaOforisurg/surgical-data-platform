import json

import pandas as pd
import pytest

from streamlit_services.publishing_service import (
    APPROVED_DRAFT_STATUS,
    PUBLISHED_DRAFT_STATUS,
    PUBLISH_EVENT_PREFIX,
    apply_approved_draft_to_gold,
    build_publish_event,
    load_publishable_drafts,
    mark_draft_published,
    save_publish_event,
    save_published_gold,
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


def _gold_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "surgeon_id": "SURG-001",
                "surgeon_name": "Ms Amina Clarke",
                "procedure_id": "ORTH_KNEE_001",
                "procedure": "Total Knee Replacement",
                "instrument_set": "Standard knee set",
                "equipment": "Tourniquet",
                "implants": "Cemented knee system",
                "preference_card_version": 2,
                "preference_card_version_label": "v2",
                "version_number": 2,
                "version_updated_by": "original-loader",
                "version_updated_at": "2026-07-01T08:00:00+00:00",
                "is_current": True,
            }
        ]
    )


def _approved_edit_draft() -> dict:
    return {
        "draft_id": "draft-123",
        "draft_type": "edit",
        "status": APPROVED_DRAFT_STATUS,
        "review_id": "review-123",
        "review_object_key": "gold/operational/draft_reviews/review-123.json",
        "surgeon_id": "SURG-001",
        "surgeon_name": "Ms Amina Clarke",
        "procedure_id": "ORTH_KNEE_001",
        "procedure": "Total Knee Replacement",
        "original": {"equipment": "Tourniquet"},
        "proposed": {"equipment": "Tourniquet and image intensifier"},
        "_object_key": "gold/operational/drafts/draft-123.json",
    }


def test_load_publishable_drafts_only_returns_approved_pending_publish_items():
    storage = FakeStorage(
        {
            "gold/operational/drafts/001.json": json.dumps(_approved_edit_draft()),
            "gold/operational/drafts/002.json": json.dumps(
                {**_approved_edit_draft(), "draft_id": "draft-456", "status": "pending_review"}
            ),
        }
    )

    drafts = load_publishable_drafts(storage, "gold/operational/drafts")

    assert len(drafts) == 1
    assert drafts[0]["draft_id"] == "draft-123"
    assert drafts[0]["_object_key"] == "gold/operational/drafts/001.json"


def test_apply_approved_edit_draft_updates_matching_gold_row_and_bumps_version():
    published = apply_approved_draft_to_gold(
        current_gold=_gold_df(),
        draft=_approved_edit_draft(),
        publisher="Clinical Admin",
        editable_fields=["equipment", "implants"],
        published_at="2026-07-20T12:00:00+00:00",
    )

    row = published.iloc[0]
    assert row["equipment"] == "Tourniquet and image intensifier"
    assert row["implants"] == "Cemented knee system"
    assert row["preference_card_version"] == 3
    assert row["preference_card_version_label"] == "v3"
    assert row["version_updated_by"] == "Clinical Admin"
    assert row["version_updated_at"] == "2026-07-20T12:00:00+00:00"


def test_apply_approved_create_draft_appends_new_gold_row():
    draft = {
        **_approved_edit_draft(),
        "draft_type": "create",
        "surgeon_id": "SURG-002",
        "surgeon_name": "Mr Kwame Mensah",
        "procedure_id": "ORTH_HIP_001",
        "procedure": "Total Hip Replacement",
        "specialty": "Orthopaedics",
        "subspecialty": "Hip",
        "proposed": {
            "instrument_set": "Primary hip set",
            "equipment": "Traction table",
            "implants": "Uncemented hip system",
        },
    }

    published = apply_approved_draft_to_gold(
        current_gold=_gold_df(),
        draft=draft,
        publisher="Clinical Admin",
        editable_fields=["instrument_set", "equipment", "implants"],
        published_at="2026-07-20T12:00:00+00:00",
    )

    new_row = published[published["surgeon_id"] == "SURG-002"].iloc[0]
    assert len(published) == 2
    assert new_row["procedure"] == "Total Hip Replacement"
    assert new_row["equipment"] == "Traction table"
    assert new_row["preference_card_version"] == 1


def test_non_approved_drafts_and_unmatched_edits_are_not_published():
    with pytest.raises(ValueError, match="Only approved_pending_publish"):
        apply_approved_draft_to_gold(
            current_gold=_gold_df(),
            draft={**_approved_edit_draft(), "status": "pending_review"},
            publisher="Clinical Admin",
            editable_fields=["equipment"],
        )

    with pytest.raises(ValueError, match="does not match"):
        apply_approved_draft_to_gold(
            current_gold=_gold_df(),
            draft={**_approved_edit_draft(), "procedure_id": "UNKNOWN"},
            publisher="Clinical Admin",
            editable_fields=["equipment"],
        )


def test_publish_event_gold_outputs_and_draft_status_are_archived():
    storage = FakeStorage({})
    draft = _approved_edit_draft()
    publish_event = build_publish_event(
        draft=draft,
        publisher="Clinical Admin",
        publisher_email="admin@example.com",
        publisher_roles=("admin",),
        published_gold_key="",
        latest_gold_key="gold/operational/latest/gold_operational_preference_cards.csv",
        row_count=1,
        published_at="2026-07-20T12:00:00+00:00",
    )

    published_key = save_published_gold(
        storage,
        _gold_df(),
        publish_event["publish_id"],
        "gold/operational/latest/gold_operational_preference_cards.csv",
    )
    publish_event = {**publish_event, "published_gold_key": published_key}
    event_key = save_publish_event(storage, publish_event)
    storage.objects[draft["_object_key"]] = json.dumps(draft)
    updated_draft = mark_draft_published(storage, draft, publish_event, event_key)

    assert published_key.startswith("gold/operational/published/")
    assert "gold/operational/latest/gold_operational_preference_cards.csv" in storage.objects
    assert event_key.startswith(f"{PUBLISH_EVENT_PREFIX}/")
    assert json.loads(storage.objects[event_key])["publisher_email"] == "admin@example.com"
    assert updated_draft["status"] == PUBLISHED_DRAFT_STATUS
    assert json.loads(storage.objects[draft["_object_key"]])["publish_event_key"] == event_key
