from streamlit_services.access_control import AppUser
from streamlit_services.user_registry_service import (
    initial_registry_status,
    list_access_requests,
    merge_registry_user,
    resolve_access_request,
    submit_access_request,
    sync_user_with_registry,
    update_user_access,
)


class FakeRepository:
    def __init__(self, row):
        self.row = row
        self.initialised = False
        self.seen_payload = None

    def initialise(self):
        self.initialised = True

    def upsert_app_user_seen(self, **kwargs):
        self.seen_payload = kwargs
        return self.row

    def update_app_user_access(self, **kwargs):
        self.seen_payload = kwargs
        return {
            "user_email": kwargs["user_email"],
            "display_name": kwargs["display_name"],
            "roles": kwargs["roles"],
            "status": kwargs["status"],
        }

    def create_access_request(self, **kwargs):
        self.seen_payload = kwargs
        return {
            "access_request_id": "request-1",
            "user_email": kwargs["user_email"],
            "display_name": kwargs["display_name"],
            "requested_roles": kwargs["requested_roles"],
            "requested_organisation_name": kwargs["requested_organisation_name"],
            "reason": kwargs["reason"],
            "status": "pending_review",
        }

    def list_access_requests(self, **kwargs):
        self.seen_payload = kwargs
        return [
            {
                "access_request_id": "request-1",
                "user_email": "viewer@example.com",
                "status": kwargs.get("status") or "pending_review",
            }
        ]

    def resolve_access_request(self, **kwargs):
        self.seen_payload = kwargs
        return {
            "access_request_id": kwargs["access_request_id"],
            "status": kwargs["decision"],
            "reviewed_by_email": kwargs["actor_email"],
        }


def test_initial_registry_status_keeps_unprivileged_users_pending():
    viewer = AppUser(
        email="viewer@example.com",
        display_name="Viewer",
        roles=("authenticated",),
    )
    editor = AppUser(
        email="editor@example.com",
        display_name="Editor",
        roles=("authenticated", "editor"),
    )

    assert initial_registry_status(viewer) == "pending_access"
    assert initial_registry_status(editor) == "active"


def test_merge_registry_user_combines_verified_identity_with_registry_status():
    identity_user = AppUser(
        email="person@example.com",
        display_name="Identity Name",
        roles=("authenticated",),
    )
    registry_row = {
        "user_email": "person@example.com",
        "display_name": "Registered Name",
        "roles": ["editor"],
        "status": "active",
    }

    merged = merge_registry_user(identity_user, registry_row)

    assert merged.email == "person@example.com"
    assert merged.display_name == "Registered Name"
    assert merged.roles == ("authenticated", "editor")
    assert merged.status == "active"
    assert merged.can_submit_preferences is True


def test_merge_registry_user_respects_suspended_status():
    identity_user = AppUser(
        email="admin@example.com",
        display_name="Admin",
        roles=("admin", "authenticated"),
    )

    merged = merge_registry_user(
        identity_user,
        {
            "user_email": "admin@example.com",
            "display_name": "Admin",
            "roles": ["admin"],
            "status": "suspended",
        },
    )

    assert merged.roles == ("admin", "authenticated")
    assert merged.status == "suspended"
    assert merged.can_publish_preferences is False


def test_sync_user_without_postgres_uses_identity_roles():
    user = AppUser(
        email="editor@example.com",
        display_name="Editor",
        roles=("authenticated", "editor"),
    )

    synced, warning = sync_user_with_registry(user, settings=None)

    assert synced == user
    assert warning == "Postgres user registry is not configured; using identity roles only."


def test_sync_user_without_identity_returns_empty_result():
    synced, warning = sync_user_with_registry(None, settings=None)

    assert synced is None
    assert warning is None


def test_sync_user_registers_seen_identity_and_returns_registry_roles():
    user = AppUser(
        email="viewer@example.com",
        display_name="Viewer",
        roles=("authenticated",),
    )
    repository = FakeRepository(
        {
            "user_email": "viewer@example.com",
            "display_name": "Approved Editor",
            "roles": ["editor"],
            "status": "active",
        }
    )

    synced, warning = sync_user_with_registry(
        user,
        settings=object(),
        auth_provider="azure_container_apps",
        repository_factory=lambda settings: repository,
    )

    assert warning is None
    assert repository.initialised is True
    assert repository.seen_payload == {
        "user_email": "viewer@example.com",
        "display_name": "Viewer",
        "roles": ["authenticated"],
        "status": "pending_access",
        "auth_provider": "azure_container_apps",
        "organisation_id": "default",
        "organisation_name": "Surgeon Preference Demo",
    }
    assert synced.display_name == "Approved Editor"
    assert synced.roles == ("authenticated", "editor")
    assert synced.status == "active"


def test_update_user_access_writes_admin_change_request():
    actor = AppUser(
        email="admin@example.com",
        display_name="Admin",
        roles=("admin", "authenticated"),
    )
    repository = FakeRepository(row=None)

    updated, error = update_user_access(
        settings=object(),
        target_email="Person@Example.Com",
        display_name="Person",
        roles=["authenticated", "editor"],
        status="active",
        actor=actor,
        repository_factory=lambda settings: repository,
    )

    assert error is None
    assert repository.initialised is True
    assert repository.seen_payload == {
        "user_email": "Person@Example.Com",
        "display_name": "Person",
        "roles": ["authenticated", "editor"],
        "status": "active",
        "actor_email": "admin@example.com",
        "actor_name": "Admin",
        "actor_roles": ["admin", "authenticated"],
        "organisation_id": "default",
        "organisation_name": "Surgeon Preference Demo",
    }
    assert updated == {
        "user_email": "Person@Example.Com",
        "display_name": "Person",
        "roles": ["authenticated", "editor"],
        "status": "active",
    }


def test_update_user_access_returns_validation_errors():
    actor = AppUser(
        email="admin@example.com",
        display_name="Admin",
        roles=("admin", "authenticated"),
    )

    updated, error = update_user_access(
        settings=None,
        target_email="person@example.com",
        display_name="Person",
        roles=["editor"],
        status="active",
        actor=actor,
    )

    assert updated is None
    assert error == "Postgres user registry is not configured."


def test_submit_access_request_requires_identity():
    request, error = submit_access_request(
        settings=object(),
        user=None,
        requested_roles=["editor"],
        requested_organisation_name="Demo Hospital",
        reason="I need to manage cards.",
    )

    assert request is None
    assert error == "Sign in before requesting access."


def test_submit_access_request_writes_pending_request():
    user = AppUser(
        email="viewer@example.com",
        display_name="Viewer",
        roles=("authenticated",),
        organisation_id="hospital-a",
        organisation_name="Hospital A",
    )
    repository = FakeRepository(row=None)

    request, error = submit_access_request(
        settings=object(),
        user=user,
        requested_roles=["editor"],
        requested_organisation_name="Hospital A",
        reason="I prepare theatre preference cards.",
        repository_factory=lambda settings: repository,
    )

    assert error is None
    assert repository.initialised is True
    assert repository.seen_payload == {
        "user_email": "viewer@example.com",
        "display_name": "Viewer",
        "requested_roles": ["authenticated", "editor"],
        "requested_organisation_name": "Hospital A",
        "reason": "I prepare theatre preference cards.",
        "organisation_id": "hospital-a",
        "organisation_name": "Hospital A",
    }
    assert request["status"] == "pending_review"


def test_list_access_requests_uses_repository_filters():
    repository = FakeRepository(row=None)

    requests, error = list_access_requests(
        settings=object(),
        organisation_id="hospital-a",
        status="pending_review",
        repository_factory=lambda settings: repository,
    )

    assert error is None
    assert repository.initialised is True
    assert repository.seen_payload == {
        "organisation_id": "hospital-a",
        "status": "pending_review",
    }
    assert requests[0]["access_request_id"] == "request-1"


def test_resolve_access_request_records_admin_decision():
    actor = AppUser(
        email="admin@example.com",
        display_name="Admin",
        roles=("admin", "authenticated"),
    )
    repository = FakeRepository(row=None)

    request, error = resolve_access_request(
        settings=object(),
        access_request_id="request-1",
        decision="approved",
        actor=actor,
        repository_factory=lambda settings: repository,
    )

    assert error is None
    assert repository.initialised is True
    assert repository.seen_payload == {
        "access_request_id": "request-1",
        "decision": "approved",
        "actor_email": "admin@example.com",
        "actor_name": "Admin",
        "actor_roles": ["admin", "authenticated"],
    }
    assert request["reviewed_by_email"] == "admin@example.com"
