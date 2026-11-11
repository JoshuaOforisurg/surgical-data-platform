from streamlit_services.access_control import AppUser
from application_services.preference_drafts import submit_preference_draft


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def put_text(self, key, text, content_type):
        self.objects[key] = (text, content_type)


class FakeRepository:
    def __init__(self, membership, audit_error=None):
        self.membership = membership
        self.audit_error = audit_error
        self.recorded_draft = None
        self.initialised = False

    def initialise(self):
        self.initialised = True

    def get_user_membership(self, **_kwargs):
        return self.membership

    def record_draft_submission(self, draft, object_key):
        if self.audit_error:
            raise RuntimeError(self.audit_error)
        self.recorded_draft = (draft, object_key)


def test_draft_submission_is_ui_independent_and_tenant_scoped():
    user = AppUser(
        email="editor@example.com",
        display_name="Editor",
        roles=("authenticated", "editor"),
        organisation_id="hospital-a",
        organisation_name="Hospital A",
    )
    repository = FakeRepository({
        "organisation_id": "hospital-a",
        "roles": ["editor"],
        "status": "active",
        "organisation_status": "active",
    })
    storage = FakeStorage()

    result = submit_preference_draft(
        {"draft_id": "draft-1", "draft_type": "create", "proposed": {"consumables": "Hip pack"}},
        user,
        settings=object(),
        storage_factory=lambda: storage,
        repository_factory=lambda _settings: repository,
        submitted_at="2026-10-18T12:00:00+00:00",
    )

    assert result.audit_saved is True
    assert result.object_key.startswith("gold/operational/drafts/hospital-a/20261018_120000_")
    assert result.draft["organisation_id"] == "hospital-a"
    assert result.draft["submitter_email"] == user.email
    assert repository.recorded_draft == (result.draft, result.object_key)
    assert result.object_key in storage.objects


def test_draft_submission_fails_closed_when_membership_role_is_revoked():
    user = AppUser(
        email="editor@example.com",
        display_name="Editor",
        roles=("authenticated", "editor"),
        organisation_id="hospital-a",
    )
    repository = FakeRepository({
        "organisation_id": "hospital-a",
        "roles": ["authenticated"],
        "status": "active",
        "organisation_status": "active",
    })
    storage = FakeStorage()

    try:
        submit_preference_draft(
            {"draft_id": "draft-2", "draft_type": "create"},
            user,
            settings=object(),
            storage_factory=lambda: storage,
            repository_factory=lambda _settings: repository,
        )
    except PermissionError as exc:
        assert "does not allow this action" in str(exc)
    else:
        raise AssertionError("Revoked editor access must block draft submission.")

    assert storage.objects == {}
    assert repository.recorded_draft is None


def test_draft_service_reports_partial_storage_success_when_audit_fails():
    user = AppUser(
        email="editor@example.com",
        display_name="Editor",
        roles=("authenticated", "editor"),
        organisation_id="hospital-a",
    )
    repository = FakeRepository({
        "organisation_id": "hospital-a",
        "roles": ["editor"],
        "status": "active",
        "organisation_status": "active",
    }, audit_error="Postgres unavailable")
    storage = FakeStorage()

    result = submit_preference_draft(
        {"draft_id": "draft-3", "draft_type": "create"},
        user,
        settings=object(),
        storage_factory=lambda: storage,
        repository_factory=lambda _settings: repository,
    )

    assert result.audit_saved is False
    assert result.audit_error == "Postgres unavailable"
    assert result.object_key in storage.objects
