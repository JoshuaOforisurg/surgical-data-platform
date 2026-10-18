from __future__ import annotations

from typing import Any

from bronze_Ingestion.catalog import BronzeCatalogRepository
from config.settings import PostgresSettings
from streamlit_services.access_control import (
    ACTIVE_STATUS,
    ADMIN_ROLE,
    AppUser,
    AUTHENTICATED_ROLE,
    DEFAULT_ORGANISATION_ID,
    EDITOR_ROLE,
    PENDING_ACCESS_STATUS,
    REVIEWER_ROLE,
)


PRIVILEGED_ROLES = {EDITOR_ROLE, REVIEWER_ROLE, ADMIN_ROLE}


def initial_registry_status(user: AppUser) -> str:
    if PRIVILEGED_ROLES & set(user.roles):
        return ACTIVE_STATUS
    return PENDING_ACCESS_STATUS


def choose_active_membership(
    memberships: list[dict[str, Any]],
    selected_organisation_id: str | None,
    default_organisation_id: str | None,
) -> dict[str, Any] | None:
    active = [
        membership
        for membership in memberships
        if str(membership.get("status") or "").strip().lower() == ACTIVE_STATUS
        and str(membership.get("organisation_status") or "").strip().lower() == ACTIVE_STATUS
    ]
    selected_id = str(selected_organisation_id or "").strip()
    default_id = str(default_organisation_id or "").strip()
    return next(
        (item for item in active if item.get("organisation_id") == selected_id),
        next(
            (item for item in active if item.get("organisation_id") == default_id),
            active[0] if active else None,
        ),
    )


def list_user_memberships(
    settings: PostgresSettings | None,
    user_email: str | None,
    repository_factory=BronzeCatalogRepository,
) -> tuple[list[dict[str, Any]], str | None]:
    if not user_email:
        return [], None
    if settings is None:
        return [], "Postgres user registry is not configured."

    try:
        repository = repository_factory(settings)
        repository.initialise()
        memberships = repository.list_user_memberships(user_email)
    except Exception as exc:
        return [], f"Organisation memberships could not be loaded: {exc}"

    return memberships, None


def require_active_membership_role(
    settings: PostgresSettings | None,
    user: AppUser | None,
    required_roles: set[str],
    organisation_id: str | None = None,
    repository_factory=BronzeCatalogRepository,
) -> tuple[dict[str, Any] | None, str | None]:
    """Re-resolve tenant authorization immediately before a protected write."""
    if user is None:
        return None, "Sign in before performing this action."
    if settings is None:
        return None, "Postgres membership registry is unavailable; the action was blocked."

    requested_org = str(organisation_id or user.organisation_id or "").strip()
    if not requested_org or requested_org != user.organisation_id:
        return None, "The requested organisation does not match the authenticated workspace."

    try:
        repository = repository_factory(settings)
        repository.initialise()
        membership = repository.get_user_membership(
            user_email=user.email,
            organisation_id=requested_org,
        )
    except Exception:
        return None, "Postgres membership registry is unavailable; the action was blocked."

    if not membership:
        return None, "An active membership in this organisation is required."
    if (
        str(membership.get("status") or "").lower() != ACTIVE_STATUS
        or str(membership.get("organisation_id") or "") != requested_org
        or str(membership.get("organisation_status") or ACTIVE_STATUS).lower() != ACTIVE_STATUS
    ):
        return None, "An active membership in this organisation is required."

    actual_roles = {str(role).strip().lower() for role in membership.get("roles") or []}
    allowed_roles = {str(role).strip().lower() for role in required_roles}
    if not actual_roles.intersection(allowed_roles):
        return None, "Your active organisation membership does not allow this action."
    return membership, None


def merge_registry_user(identity_user: AppUser, registry_row: dict[str, Any] | None) -> AppUser:
    if not registry_row:
        return AppUser(
            email=identity_user.email,
            display_name=identity_user.display_name,
            roles=identity_user.roles,
            status=initial_registry_status(identity_user),
            organisation_id=identity_user.organisation_id,
            organisation_name=identity_user.organisation_name,
            identity_provider=identity_user.identity_provider,
            identity_subject=identity_user.identity_subject,
        )

    registry_roles = {
        str(role).strip().lower()
        for role in registry_row.get("roles") or []
        if str(role).strip()
    }
    roles = tuple(sorted(registry_roles | {AUTHENTICATED_ROLE}))
    status = str(registry_row.get("status") or initial_registry_status(identity_user)).strip().lower()
    display_name = str(registry_row.get("display_name") or identity_user.display_name).strip()
    organisation_id = str(
        registry_row.get("organisation_id")
        or identity_user.organisation_id
        or DEFAULT_ORGANISATION_ID
    ).strip()
    organisation_name = str(
        registry_row.get("organisation_name")
        or identity_user.organisation_name
        or "Surgeon Preference Demo"
    ).strip()

    return AppUser(
        email=identity_user.email,
        display_name=display_name or identity_user.email,
        roles=roles,
        status=status,
        organisation_id=organisation_id or DEFAULT_ORGANISATION_ID,
        organisation_name=organisation_name or "Surgeon Preference Demo",
        identity_provider=identity_user.identity_provider,
        identity_subject=identity_user.identity_subject,
    )


def sync_user_with_registry(
    user: AppUser | None,
    settings: PostgresSettings | None,
    auth_provider: str = "streamlit",
    repository_factory=BronzeCatalogRepository,
    organisation_id: str | None = None,
) -> tuple[AppUser | None, str | None]:
    if user is None:
        return None, None
    if settings is None:
        return None, "Postgres user registry is not configured; protected actions are disabled."

    try:
        repository = repository_factory(settings)
        repository.initialise()
        repository.upsert_app_user_seen(
            user_email=user.email,
            display_name=user.display_name,
            auth_provider=user.identity_provider or auth_provider,
            identity_subject=user.identity_subject,
        )
        resolved_organisation_id = str(organisation_id or user.organisation_id).strip()
        registry_row = repository.get_user_membership(
            user_email=user.email,
            organisation_id=resolved_organisation_id,
        )
    except Exception as exc:
        return None, f"Postgres user registry could not be reached; protected actions are disabled: {exc}"

    if registry_row is None:
        return AppUser(
            email=user.email,
            display_name=user.display_name,
            roles=(AUTHENTICATED_ROLE,),
            status=PENDING_ACCESS_STATUS,
            organisation_id=resolved_organisation_id,
            organisation_name=user.organisation_name,
            identity_provider=user.identity_provider,
            identity_subject=user.identity_subject,
        ), None

    return merge_registry_user(user, registry_row), None


def update_user_access(
    settings: PostgresSettings | None,
    target_email: str,
    display_name: str,
    roles: list[str],
    status: str,
    actor: AppUser,
    repository_factory=BronzeCatalogRepository,
) -> tuple[dict[str, Any] | None, str | None]:
    if settings is None:
        return None, "Postgres user registry is not configured."
    _, access_error = require_active_membership_role(
        settings, actor, {ADMIN_ROLE}, repository_factory=repository_factory
    )
    if access_error:
        return None, access_error

    try:
        repository = repository_factory(settings)
        repository.initialise()
        updated = repository.update_app_user_access(
            user_email=target_email,
            display_name=display_name,
            roles=roles,
            status=status,
            actor_email=actor.email,
            actor_name=actor.display_name,
            actor_roles=list(actor.roles),
            organisation_id=actor.organisation_id,
            organisation_name=actor.organisation_name,
        )
    except ValueError as exc:
        return None, str(exc)
    except Exception as exc:
        return None, f"Postgres user registry could not be updated: {exc}"

    return updated, None


def submit_access_request(
    settings: PostgresSettings | None,
    user: AppUser | None,
    requested_roles: list[str],
    requested_organisation_name: str,
    reason: str,
    repository_factory=BronzeCatalogRepository,
) -> tuple[dict[str, Any] | None, str | None]:
    if user is None:
        return None, "Sign in before requesting access."
    if settings is None:
        return None, "Postgres user registry is not configured."

    allowed_roles = {AUTHENTICATED_ROLE, EDITOR_ROLE, REVIEWER_ROLE, ADMIN_ROLE}
    roles = sorted({role for role in requested_roles if role in allowed_roles})
    if AUTHENTICATED_ROLE not in roles:
        roles = [AUTHENTICATED_ROLE, *roles]

    try:
        repository = repository_factory(settings)
        repository.initialise()
        request = repository.create_access_request(
            user_email=user.email,
            display_name=user.display_name,
            requested_roles=roles,
            requested_organisation_name=requested_organisation_name,
            reason=reason,
            organisation_id=user.organisation_id,
            organisation_name=user.organisation_name,
        )
    except ValueError as exc:
        return None, str(exc)
    except Exception as exc:
        return None, f"Access request could not be saved: {exc}"

    return request, None


def list_access_requests(
    settings: PostgresSettings | None,
    organisation_id: str | None = None,
    status: str | None = None,
    user_email: str | None = None,
    repository_factory=BronzeCatalogRepository,
) -> tuple[list[dict[str, Any]], str | None]:
    if settings is None:
        return [], "Postgres user registry is not configured."

    try:
        repository = repository_factory(settings)
        repository.initialise()
        requests = repository.list_access_requests(
            organisation_id=organisation_id,
            status=status,
            user_email=user_email,
        )
    except Exception as exc:
        return [], f"Access requests could not be loaded: {exc}"

    return requests, None


def resolve_access_request(
    settings: PostgresSettings | None,
    access_request_id: str,
    decision: str,
    actor: AppUser,
    repository_factory=BronzeCatalogRepository,
) -> tuple[dict[str, Any] | None, str | None]:
    if settings is None:
        return None, "Postgres user registry is not configured."
    _, access_error = require_active_membership_role(
        settings, actor, {ADMIN_ROLE}, repository_factory=repository_factory
    )
    if access_error:
        return None, access_error

    try:
        repository = repository_factory(settings)
        repository.initialise()
        request = repository.resolve_access_request(
            access_request_id=access_request_id,
            organisation_id=actor.organisation_id,
            decision=decision,
            actor_email=actor.email,
            actor_name=actor.display_name,
            actor_roles=list(actor.roles),
        )
    except ValueError as exc:
        return None, str(exc)
    except Exception as exc:
        return None, f"Access request could not be updated: {exc}"

    return request, None
