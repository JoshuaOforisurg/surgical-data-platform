import base64
import json
from dataclasses import dataclass
from typing import Any, Mapping


REVIEWER_ROLE = "reviewer"
ADMIN_ROLE = "admin"
EDITOR_ROLE = "editor"
AUTHENTICATED_ROLE = "authenticated"
ACTIVE_STATUS = "active"
PENDING_ACCESS_STATUS = "pending_access"
SUSPENDED_STATUS = "suspended"
DEFAULT_ORGANISATION_ID = "default"
EMAIL_CLAIM_TYPES = {
    "email",
    "emails",
    "preferred_username",
    "upn",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
}
NAME_CLAIM_TYPES = {
    "name",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
}
ROLE_CLAIM_TYPES = {
    "roles",
    "role",
    "http://schemas.microsoft.com/ws/2008/06/identity/claims/role",
}


@dataclass(frozen=True)
class AppUser:
    email: str
    display_name: str
    roles: tuple[str, ...]
    status: str = ACTIVE_STATUS
    organisation_id: str = DEFAULT_ORGANISATION_ID
    organisation_name: str = "Surgeon Preference Demo"

    @property
    def is_active(self) -> bool:
        return self.status == ACTIVE_STATUS

    @property
    def can_submit_preferences(self) -> bool:
        return self.is_active and bool({EDITOR_ROLE, REVIEWER_ROLE, ADMIN_ROLE} & set(self.roles))

    @property
    def can_review_preferences(self) -> bool:
        return self.is_active and (REVIEWER_ROLE in self.roles or ADMIN_ROLE in self.roles)

    @property
    def can_publish_preferences(self) -> bool:
        return self.is_active and ADMIN_ROLE in self.roles

    @property
    def can_manage_users(self) -> bool:
        return self.is_active and ADMIN_ROLE in self.roles


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


def _value_from_headers(headers: Mapping[str, str], name: str) -> str:
    expected = name.lower()
    for key, value in headers.items():
        if key.lower() == expected:
            return str(value or "").strip()
    return ""


def _decode_client_principal(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.b64decode(padded).decode("utf-8")
        payload = json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _claim_values(principal: Mapping[str, Any], claim_types: set[str]) -> list[str]:
    values: list[str] = []
    for claim in principal.get("claims") or []:
        if not isinstance(claim, Mapping):
            continue
        claim_type = str(claim.get("typ") or "").lower()
        claim_value = str(claim.get("val") or "").strip()
        if claim_type in claim_types and claim_value:
            values.append(claim_value)
    return values


def _roles_for_email(email: str, env: Mapping[str, str], identity_roles: list[str] | None = None) -> tuple[str, ...]:
    email = normalise_email(email)
    editor_allowlist = parse_email_list(env.get("APP_EDITOR_ALLOWLIST"))
    reviewer_allowlist = parse_email_list(env.get("APP_REVIEWER_ALLOWLIST"))
    admin_allowlist = parse_email_list(env.get("APP_ADMIN_ALLOWLIST"))
    roles = {
        role.strip().lower()
        for role in identity_roles or []
        if role.strip().lower() in {AUTHENTICATED_ROLE, EDITOR_ROLE, REVIEWER_ROLE, ADMIN_ROLE}
    }

    if email:
        roles.add(AUTHENTICATED_ROLE)
    if email in editor_allowlist:
        roles.add(EDITOR_ROLE)
    if email in reviewer_allowlist:
        roles.add(REVIEWER_ROLE)
    if email in admin_allowlist:
        roles.add(ADMIN_ROLE)

    return tuple(sorted(roles))


def load_user_from_env(env: Mapping[str, str]) -> AppUser | None:
    email = normalise_email(
        env.get("APP_CURRENT_USER_EMAIL")
        or env.get("STREAMLIT_USER_EMAIL")
        or env.get("AUTHENTICATED_USER_EMAIL")
    )
    if not email:
        return None

    display_name = (
        env.get("APP_CURRENT_USER_NAME")
        or env.get("STREAMLIT_USER_NAME")
        or env.get("AUTHENTICATED_USER_NAME")
        or email
    ).strip()

    return AppUser(
        email=email,
        display_name=display_name,
        roles=_roles_for_email(email, env),
        organisation_id=(env.get("APP_ORGANISATION_ID") or DEFAULT_ORGANISATION_ID).strip()
        or DEFAULT_ORGANISATION_ID,
        organisation_name=(env.get("APP_ORGANISATION_NAME") or "Surgeon Preference Demo").strip()
        or "Surgeon Preference Demo",
    )


def load_user_from_headers(headers: Mapping[str, str], env: Mapping[str, str]) -> AppUser | None:
    principal = _decode_client_principal(_value_from_headers(headers, "x-ms-client-principal"))
    claim_emails = _claim_values(principal, EMAIL_CLAIM_TYPES)
    principal_name = _value_from_headers(headers, "x-ms-client-principal-name")
    email = normalise_email(next((value for value in claim_emails if "@" in value), ""))
    if not email and "@" in principal_name:
        email = normalise_email(principal_name)
    if not email:
        return None

    display_name = (
        next(iter(_claim_values(principal, NAME_CLAIM_TYPES)), "")
        or principal.get("userDetails")
        or principal_name
        or email
    )
    identity_roles = _claim_values(principal, ROLE_CLAIM_TYPES)
    return AppUser(
        email=email,
        display_name=str(display_name).strip() or email,
        roles=_roles_for_email(email, env, identity_roles),
        organisation_id=(env.get("APP_ORGANISATION_ID") or DEFAULT_ORGANISATION_ID).strip()
        or DEFAULT_ORGANISATION_ID,
        organisation_name=(env.get("APP_ORGANISATION_NAME") or "Surgeon Preference Demo").strip()
        or "Surgeon Preference Demo",
    )


def load_current_user(
    env: Mapping[str, str],
    headers: Mapping[str, str] | None = None,
) -> AppUser | None:
    if headers:
        header_user = load_user_from_headers(headers, env)
        if header_user:
            return header_user
    return load_user_from_env(env)


def review_block_reason(user: AppUser | None, review_feature_enabled: bool) -> str | None:
    if not review_feature_enabled:
        return "Review decisions are disabled for this deployment."
    if user is None:
        return "No authenticated reviewer identity was found."
    if not user.is_active:
        return f"{user.email} is not active in the Surgeon Preference user registry."
    if not user.can_review_preferences:
        return f"{user.email} is not authorised to review preference-card drafts."
    return None


def publish_block_reason(user: AppUser | None, publish_feature_enabled: bool) -> str | None:
    if not publish_feature_enabled:
        return "Publishing approved drafts is disabled for this deployment."
    if user is None:
        return "No authenticated publisher identity was found."
    if not user.is_active:
        return f"{user.email} is not active in the Surgeon Preference user registry."
    if not user.can_publish_preferences:
        return f"{user.email} is not authorised to publish preference-card drafts."
    return None


def submission_block_reason(user: AppUser | None, submission_feature_enabled: bool) -> str | None:
    if not submission_feature_enabled:
        return "Draft submissions are disabled for this deployment."
    if user is None:
        return "No authenticated submitter identity was found."
    if not user.is_active:
        return f"{user.email} is not active in the Surgeon Preference user registry."
    if not user.can_submit_preferences:
        return f"{user.email} is not authorised to create or edit preference-card drafts."
    return None


def user_management_block_reason(user: AppUser | None) -> str | None:
    if user is None:
        return "No authenticated administrator identity was found."
    if not user.is_active:
        return f"{user.email} is not active in the Surgeon Preference user registry."
    if not user.can_manage_users:
        return f"{user.email} is not authorised to manage Surgeon Preference users."
    return None
