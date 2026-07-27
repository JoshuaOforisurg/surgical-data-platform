import base64
import json

from streamlit_services.access_control import (
    AppUser,
    load_current_user,
    load_user_from_headers,
    load_user_from_env,
    parse_email_list,
    publish_block_reason,
    review_block_reason,
    submission_block_reason,
    user_management_block_reason,
)


def test_parse_email_list_normalises_and_ignores_blanks():
    assert parse_email_list(" Reviewer@Hospital.Org, ,admin@example.com ") == {
        "reviewer@hospital.org",
        "admin@example.com",
    }


def test_missing_identity_cannot_review():
    assert load_user_from_env({}) is None
    assert review_block_reason(None, review_feature_enabled=True) == (
        "No authenticated reviewer identity was found."
    )


def test_known_viewer_is_authenticated_but_not_authorised():
    user = load_user_from_env(
        {
            "APP_CURRENT_USER_EMAIL": "viewer@example.com",
            "APP_REVIEWER_ALLOWLIST": "reviewer@example.com",
        }
    )

    assert user is not None
    assert user.roles == ("authenticated",)
    assert review_block_reason(user, review_feature_enabled=True) == (
        "viewer@example.com is not authorised to review preference-card drafts."
    )


def test_reviewer_allowlist_grants_review_permission():
    user = load_user_from_env(
        {
            "APP_CURRENT_USER_EMAIL": "Reviewer@Example.Com",
            "APP_CURRENT_USER_NAME": "Theatre Reviewer",
            "APP_REVIEWER_ALLOWLIST": "reviewer@example.com",
        }
    )

    assert user is not None
    assert user.email == "reviewer@example.com"
    assert user.display_name == "Theatre Reviewer"
    assert user.can_review_preferences is True
    assert review_block_reason(user, review_feature_enabled=True) is None


def test_admin_allowlist_grants_publish_permission():
    user = load_user_from_env(
        {
            "APP_CURRENT_USER_EMAIL": "admin@example.com",
            "APP_ADMIN_ALLOWLIST": "admin@example.com",
        }
    )

    assert user is not None
    assert user.can_review_preferences is True
    assert user.can_publish_preferences is True
    assert publish_block_reason(user, publish_feature_enabled=True) is None


def test_editor_allowlist_grants_draft_submission_only():
    user = load_user_from_env(
        {
            "APP_CURRENT_USER_EMAIL": "editor@example.com",
            "APP_EDITOR_ALLOWLIST": "editor@example.com",
        }
    )

    assert user is not None
    assert user.roles == ("authenticated", "editor")
    assert user.can_submit_preferences is True
    assert user.can_review_preferences is False
    assert submission_block_reason(user, submission_feature_enabled=True) is None
    assert review_block_reason(user, review_feature_enabled=True) == (
        "editor@example.com is not authorised to review preference-card drafts."
    )


def test_suspended_user_cannot_submit_review_or_publish():
    user = AppUser(
        email="admin@example.com",
        display_name="Admin",
        roles=("admin", "authenticated", "editor", "reviewer"),
        status="suspended",
    )

    assert submission_block_reason(user, submission_feature_enabled=True) == (
        "admin@example.com is not active in the Surgeon Preference user registry."
    )
    assert review_block_reason(user, review_feature_enabled=True) == (
        "admin@example.com is not active in the Surgeon Preference user registry."
    )
    assert publish_block_reason(user, publish_feature_enabled=True) == (
        "admin@example.com is not active in the Surgeon Preference user registry."
    )
    assert user_management_block_reason(user) == (
        "admin@example.com is not active in the Surgeon Preference user registry."
    )


def test_only_active_admin_can_manage_users():
    admin = AppUser(
        email="admin@example.com",
        display_name="Admin",
        roles=("admin", "authenticated"),
    )
    editor = AppUser(
        email="editor@example.com",
        display_name="Editor",
        roles=("authenticated", "editor"),
    )

    assert user_management_block_reason(admin) is None
    assert user_management_block_reason(editor) == (
        "editor@example.com is not authorised to manage Surgeon Preference users."
    )
    assert user_management_block_reason(None) == (
        "No authenticated administrator identity was found."
    )


def test_azure_client_principal_header_loads_authenticated_user():
    principal = {
        "auth_typ": "aad",
        "name_typ": "name",
        "role_typ": "roles",
        "claims": [
            {"typ": "preferred_username", "val": "Reviewer@Hospital.Org"},
            {"typ": "name", "val": "Theatre Reviewer"},
        ],
    }
    encoded = base64.b64encode(json.dumps(principal).encode("utf-8")).decode("utf-8")

    user = load_user_from_headers(
        {
            "X-MS-CLIENT-PRINCIPAL": encoded,
            "X-MS-CLIENT-PRINCIPAL-NAME": "Reviewer@Hospital.Org",
        },
        {"APP_REVIEWER_ALLOWLIST": "reviewer@hospital.org"},
    )

    assert user is not None
    assert user.email == "reviewer@hospital.org"
    assert user.display_name == "Theatre Reviewer"
    assert user.roles == ("authenticated", "reviewer")
    assert user.can_review_preferences is True


def test_current_user_prefers_verified_headers_over_local_env_identity():
    user = load_current_user(
        {
            "APP_CURRENT_USER_EMAIL": "local@example.com",
            "APP_REVIEWER_ALLOWLIST": "header@example.com",
        },
        {"X-MS-CLIENT-PRINCIPAL-NAME": "header@example.com"},
    )

    assert user is not None
    assert user.email == "header@example.com"
    assert user.roles == ("authenticated", "reviewer")


def test_review_feature_flag_blocks_even_allowed_reviewers():
    user = load_user_from_env(
        {
            "APP_CURRENT_USER_EMAIL": "reviewer@example.com",
            "APP_REVIEWER_ALLOWLIST": "reviewer@example.com",
        }
    )

    assert review_block_reason(user, review_feature_enabled=False) == (
        "Review decisions are disabled for this deployment."
    )
