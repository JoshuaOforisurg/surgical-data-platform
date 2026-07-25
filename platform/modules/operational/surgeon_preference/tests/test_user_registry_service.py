from streamlit_services.access_control import AppUser
from streamlit_services.user_registry_service import (
    initial_registry_status,
    merge_registry_user,
    sync_user_with_registry,
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
    }
    assert synced.display_name == "Approved Editor"
    assert synced.roles == ("authenticated", "editor")
    assert synced.status == "active"
