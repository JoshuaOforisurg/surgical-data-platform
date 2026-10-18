import pytest

from application_services.preference_rollbacks import rollback_preference_card
from streamlit_services.access_control import AppUser
from streamlit_services.preference_card_repository import PreferenceCardRollbackSummary


class FakeStorage:
    def __init__(self, fail=False):
        self.objects = {}
        self.fail = fail

    def put_text(self, key, text, _content_type="text/plain"):
        if self.fail:
            raise RuntimeError("object store unavailable")
        self.objects[key] = text


class FakeRepository:
    def __init__(self, membership, audit_error=None):
        self.membership = membership
        self.audit_error = audit_error
        self.rollback_called = False
        self.event = None

    def initialise(self):
        pass

    def get_user_membership(self, **_kwargs):
        return self.membership

    def rollback_to_version(self, **kwargs):
        self.rollback_called = True
        self.rollback_payload = kwargs
        return PreferenceCardRollbackSummary(
            enabled=True,
            rolled_back=True,
            card_id=kwargs["card_id"],
            rollback_version_id="rollback-v3",
            source_version_id=kwargs["source_version_id"],
            from_version_number=2,
            to_version_number=3,
            organisation_id="hospital-a",
            message="Created rollback version v3 from version v1.",
        )

    def list_current_cards(self, organisation_id):
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
            "current_version_number": 3,
            "status": "active",
            "version_id": "rollback-v3",
            "card_payload": {"consumables": "Original hip pack"},
            "source_gold_key": "gold/latest.csv",
            "published_by": "admin@example.com",
            "published_at": "2026-10-18T12:00:00+00:00",
        }]

    def record_publish_event(self, event, object_key):
        if self.audit_error:
            raise RuntimeError(self.audit_error)
        self.event = (event, object_key)


def make_repository(audit_error=None, roles=None):
    return FakeRepository({
        "organisation_id": "hospital-a",
        "roles": roles or ["admin"],
        "status": "active",
        "organisation_status": "active",
    }, audit_error=audit_error)


def actor():
    return AppUser(
        email="admin@example.com",
        display_name="Hospital Admin",
        roles=("authenticated", "admin"),
        organisation_id="hospital-a",
        organisation_name="Hospital A",
    )


def args(repository, storage, reason="Correcting the published preference"):
    return {
        "card_id": "card-a",
        "source_version_id": "version-1",
        "reason": reason,
        "actor": actor(),
        "organisation_id": "hospital-a",
        "organisation_name": "Hospital A",
        "settings": object(),
        "storage_factory": lambda: storage,
        "source_gold_key": "gold/operational/latest/cards.csv",
        "repository_factory": lambda _settings: repository,
        "audit_repository_factory": lambda _settings: repository,
        "rolled_back_at": "2026-10-18T12:00:00+00:00",
    }


def test_rollback_service_creates_and_archives_new_version():
    repository = make_repository()
    storage = FakeStorage()

    result = rollback_preference_card(**args(repository, storage))

    assert result.rolled_back is True
    assert result.audit_saved is True
    assert result.published_gold_key in storage.objects
    event, event_key = repository.event
    assert event["organisation_id"] == "hospital-a"
    assert event["publisher_roles"] == ["admin"]
    assert event["rollback_version_id"] == "rollback-v3"
    assert event["surgeon_name"] == "Surgeon A"
    assert event["procedure"] == "Total Hip Replacement"
    assert event_key == result.publish_event_key
    assert repository.rollback_payload["actor_roles"] == ["admin"]


def test_rollback_fails_closed_for_missing_reason_or_inactive_role():
    repository = make_repository(roles=["editor"])
    storage = FakeStorage()

    with pytest.raises(ValueError, match="reason is required"):
        rollback_preference_card(**args(repository, storage, reason="  "))
    with pytest.raises(PermissionError):
        rollback_preference_card(**args(repository, storage))

    assert repository.rollback_called is False
    assert storage.objects == {}


def test_rollback_reports_partial_commit_when_audit_write_fails():
    repository = make_repository(audit_error="audit unavailable")
    storage = FakeStorage()

    result = rollback_preference_card(**args(repository, storage))

    assert result.rolled_back is True
    assert result.audit_saved is False
    assert result.failure_stage == "rollback_audit"
    assert result.error == "audit unavailable"


def test_rollback_reports_operational_commit_when_storage_fails():
    repository = make_repository()
    storage = FakeStorage(fail=True)

    result = rollback_preference_card(**args(repository, storage))

    assert result.rolled_back is True
    assert result.audit_saved is False
    assert result.failure_stage == "archive_rollback"
    assert result.error == "object store unavailable"
