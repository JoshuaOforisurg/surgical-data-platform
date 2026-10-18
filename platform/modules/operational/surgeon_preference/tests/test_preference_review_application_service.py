import json

import pytest

from application_services.preference_reviews import submit_preference_review
from streamlit_services.access_control import AppUser


class FakeStorage:
    def __init__(self):
        self.objects = {"drafts/draft-1.json": "original"}

    def put_text(self, key, text, content_type="text/plain"):
        self.objects[key] = text


class FakeRepository:
    def __init__(self, membership, audit_error=None):
        self.membership = membership
        self.audit_error = audit_error
        self.review = None

    def initialise(self):
        pass

    def get_user_membership(self, **_kwargs):
        return self.membership

    def record_draft_review_decision(self, review, object_key):
        if self.audit_error:
            raise RuntimeError(self.audit_error)
        self.review = (review, object_key)


def reviewer():
    return AppUser(
        email="reviewer@example.com",
        display_name="Theatre Reviewer",
        roles=("authenticated", "reviewer"),
        organisation_id="hospital-a",
        organisation_name="Hospital A",
    )


def draft():
    return {
        "draft_id": "draft-1",
        "draft_type": "edit",
        "status": "pending_review",
        "organisation_id": "hospital-a",
        "_object_key": "drafts/draft-1.json",
        "surgeon_name": "Surgeon A",
        "procedure": "Total Hip Replacement",
        "proposed": {"consumables": "Hip pack"},
    }


def repository(membership, audit_error=None):
    return FakeRepository({
        "organisation_id": "hospital-a",
        "roles": ["reviewer"],
        "status": "active",
        "organisation_status": "active",
        **(membership or {}),
    }, audit_error=audit_error)


def test_review_application_service_records_authorized_decision():
    repo = repository({})
    storage = FakeStorage()

    result = submit_preference_review(
        draft(), reviewer(), "approved", "Checked against the procedure.",
        organisation_id="hospital-a", organisation_name="Hospital A",
        settings=object(), storage_factory=lambda: storage,
        repository_factory=lambda _settings: repo,
    )

    assert result.audit_saved is True
    assert result.review["organisation_id"] == "hospital-a"
    assert result.review["reviewer_roles"] == ["reviewer"]
    assert result.updated_draft["status"] == "approved_pending_publish"
    assert repo.review == (result.review, result.review_object_key)
    assert json.loads(storage.objects["drafts/draft-1.json"])["status"] == "approved_pending_publish"


@pytest.mark.parametrize("membership", [
    {"roles": ["editor"]},
    {"status": "suspended"},
    {"organisation_status": "suspended"},
])
def test_review_blocks_revoked_or_insufficient_membership(membership):
    repo = repository(membership)
    storage = FakeStorage()

    with pytest.raises(PermissionError):
        submit_preference_review(
            draft(), reviewer(), "approved", "", organisation_id="hospital-a",
            organisation_name="Hospital A", settings=object(),
            storage_factory=lambda: storage,
            repository_factory=lambda _settings: repo,
        )

    assert list(storage.objects) == ["drafts/draft-1.json"]
    assert repo.review is None


def test_review_reports_partial_success_if_postgres_audit_fails():
    repo = repository({}, audit_error="Postgres unavailable")
    storage = FakeStorage()

    result = submit_preference_review(
        draft(), reviewer(), "needs_changes", "Please clarify the implant details.",
        organisation_id="hospital-a", organisation_name="Hospital A",
        settings=object(), storage_factory=lambda: storage,
        repository_factory=lambda _settings: repo,
    )

    assert result.audit_saved is False
    assert result.audit_error == "Postgres unavailable"
    assert result.updated_draft["status"] == "changes_requested"
