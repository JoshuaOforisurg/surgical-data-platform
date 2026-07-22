from streamlit_services.access_control import (
    load_user_from_env,
    parse_email_list,
    review_block_reason,
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
    assert user.roles == ()
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
