import json

import pytest

from application_services.preference_publishing import publish_preference_draft
from streamlit_services.access_control import AppUser
from streamlit_services.preference_card_repository import PreferenceCardPublishSummary


class FakeStorage:
    def __init__(self, fail_on=None):
        self.objects = {}
        self.fail_on = fail_on

    def put_text(self, key, text, _content_type="text/plain"):
        if self.fail_on and self.fail_on in key:
            raise RuntimeError("object store unavailable")
        self.objects[key] = text


class FakeRepository:
    def __init__(self, membership, audit_error=None):
        self.membership = membership
        self.audit_error = audit_error
        self.published = False
        self.event = None

    def initialise(self):
        pass

    def get_user_membership(self, **_kwargs):
        return self.membership

    def publish_approved_draft(self, **kwargs):
        self.published = True
        self.publish_payload = kwargs
        return PreferenceCardPublishSummary(
            enabled=True,
            published=True,
            card_id="card-a",
            version_id="version-2",
            version_number=2,
            organisation_id="hospital-a",
            message="Published operational card version v2.",
        )

    def list_current_cards(self, organisation_id):
        assert organisation_id == "hospital-a"
        return [{
            "card_id": "card-a",
            "organisation_id": organisation_id,
            "card_key": "card-key-a",
            "surgeon_id": "surgeon-a",
            "surgeon_name": "Surgeon A",
            "procedure_id": "hip-a",
            "procedure_name": "Total Hip Replacement",
            "specialty": "Orthopaedics",
            "subspecialty": "Hip",
            "current_version_number": 2,
            "status": "active",
            "version_id": "version-2",
            "card_payload": {"consumables": "Hip pack"},
            "source_gold_key": "gold/latest.csv",
            "published_by": "admin@example.com",
            "published_at": "2026-10-18T12:00:00+00:00",
        }]

    def record_publish_event(self, event, object_key):
        if self.audit_error:
            raise RuntimeError(self.audit_error)
        self.event = (event, object_key)


def _inputs(storage, repository):
    return {
        "draft": {
            "draft_id": "draft-a",
            "draft_type": "edit",
            "status": "approved_pending_publish",
            "organisation_id": "hospital-a",
            "_object_key": "drafts/draft-a.json",
            "surgeon_id": "surgeon-a",
            "surgeon_name": "Surgeon A",
            "procedure_id": "hip-a",
            "procedure": "Total Hip Replacement",
            "review_id": "review-a",
            "proposed": {"consumables": "Hip pack"},
        },
        "publisher": AppUser(
            email="admin@example.com",
            display_name="Tenant Admin",
            roles=("authenticated", "admin"),
            organisation_id="hospital-a",
            organisation_name="Hospital A",
        ),
        "organisation_id": "hospital-a",
        "organisation_name": "Hospital A",
        "settings": object(),
        "storage_factory": lambda: storage,
        "editable_fields": ["consumables"],
        "source_gold_key": "gold/operational/latest/cards.csv",
        "repository_factory": lambda _settings: repository,
        "audit_repository_factory": lambda _settings: repository,
        "published_at": "2026-10-18T12:00:00+00:00",
    }


def test_publish_application_service_updates_card_exports_and_audits():
    repository = FakeRepository({
        "organisation_id": "hospital-a",
        "roles": ["admin"],
        "status": "active",
        "organisation_status": "active",
    })
    storage = FakeStorage()

    result = publish_preference_draft(**_inputs(storage, repository))

    assert result.operational_published is True
    assert result.audit_saved is True
    assert result.updated_draft["status"] == "published"
    assert result.published_gold_key in storage.objects
    assert result.publish_event_key in storage.objects
    event, event_key = repository.event
    assert event["organisation_id"] == "hospital-a"
    assert event["publisher_roles"] == ["admin"]
    assert event["version_id"] == "version-2"
    assert event_key == result.publish_event_key
    assert json.loads(storage.objects[result.publish_event_key])["publisher_email"] == "admin@example.com"


@pytest.mark.parametrize("draft_changes", [
    {"status": "pending_review"},
    {"organisation_id": "hospital-b"},
    {"_object_key": None},
])
def test_publish_rejects_invalid_or_cross_tenant_draft_before_database_write(draft_changes):
    repository = FakeRepository({
        "organisation_id": "hospital-a", "roles": ["admin"], "status": "active",
    })
    storage = FakeStorage()
    args = _inputs(storage, repository)
    args["draft"] = {**args["draft"], **draft_changes}

    with pytest.raises(ValueError):
        publish_preference_draft(**args)

    assert repository.published is False
    assert storage.objects == {}


def test_publish_requires_current_database_admin_membership():
    repository = FakeRepository({
        "organisation_id": "hospital-a", "roles": ["editor"], "status": "active",
    })
    storage = FakeStorage()

    with pytest.raises(PermissionError):
        publish_preference_draft(**_inputs(storage, repository))

    assert repository.published is False
    assert storage.objects == {}


def test_publish_reports_operational_success_when_postgres_audit_fails():
    repository = FakeRepository({
        "organisation_id": "hospital-a", "roles": ["admin"], "status": "active",
    }, audit_error="audit unavailable")
    storage = FakeStorage()

    result = publish_preference_draft(**_inputs(storage, repository))

    assert result.operational_published is True
    assert result.audit_saved is False
    assert result.failure_stage == "publish_audit"
    assert result.error == "audit unavailable"
    assert result.updated_draft["status"] == "published"


def test_publish_reports_partial_operational_commit_when_storage_fails():
    repository = FakeRepository({
        "organisation_id": "hospital-a", "roles": ["admin"], "status": "active",
    })
    storage = FakeStorage(fail_on="published/")

    result = publish_preference_draft(**_inputs(storage, repository))

    assert result.operational_published is True
    assert result.audit_saved is False
    assert result.failure_stage == "archive_publish"
    assert result.error == "object store unavailable"
