from dataclasses import dataclass
from typing import Mapping


REVIEWER_ROLE = "reviewer"
ADMIN_ROLE = "admin"


@dataclass(frozen=True)
class AppUser:
    email: str
    display_name: str
    roles: tuple[str, ...]

    @property
    def can_review_preferences(self) -> bool:
        return REVIEWER_ROLE in self.roles or ADMIN_ROLE in self.roles


def normalise_email(email: str | None) -> str:
    return (email or "").strip().lower()


def parse_email_list(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        normalise_email(item)
        for item in value.split(",")
        if normalise_email(item)
    }


def load_user_from_env(env: Mapping[str, str]) -> AppUser | None:
    email = normalise_email(
        env.get("APP_CURRENT_USER_EMAIL")
        or env.get("STREAMLIT_USER_EMAIL")
        or env.get("AUTHENTICATED_USER_EMAIL")
    )
    if not email:
        return None

    reviewer_allowlist = parse_email_list(env.get("APP_REVIEWER_ALLOWLIST"))
    admin_allowlist = parse_email_list(env.get("APP_ADMIN_ALLOWLIST"))
    roles: list[str] = []

    if email in reviewer_allowlist:
        roles.append(REVIEWER_ROLE)
    if email in admin_allowlist:
        roles.append(ADMIN_ROLE)

    display_name = (
        env.get("APP_CURRENT_USER_NAME")
        or env.get("STREAMLIT_USER_NAME")
        or env.get("AUTHENTICATED_USER_NAME")
        or email
    ).strip()

    return AppUser(email=email, display_name=display_name, roles=tuple(sorted(set(roles))))


def review_block_reason(user: AppUser | None, review_feature_enabled: bool) -> str | None:
    if not review_feature_enabled:
        return "Review decisions are disabled for this deployment."
    if user is None:
        return "No authenticated reviewer identity was found."
    if not user.can_review_preferences:
        return f"{user.email} is not authorised to review preference-card drafts."
    return None
