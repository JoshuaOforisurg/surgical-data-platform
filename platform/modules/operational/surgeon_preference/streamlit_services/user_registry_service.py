from __future__ import annotations

from typing import Any

from bronze_Ingestion.catalog import BronzeCatalogRepository
from config.settings import PostgresSettings
from streamlit_services.access_control import (
    ACTIVE_STATUS,
    ADMIN_ROLE,
    AppUser,
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


def merge_registry_user(identity_user: AppUser, registry_row: dict[str, Any] | None) -> AppUser:
    if not registry_row:
        return AppUser(
            email=identity_user.email,
            display_name=identity_user.display_name,
            roles=identity_user.roles,
            status=initial_registry_status(identity_user),
            organisation_id=identity_user.organisation_id,
            organisation_name=identity_user.organisation_name,
        )

    registry_roles = {
        str(role).strip().lower()
        for role in registry_row.get("roles") or []
        if str(role).strip()
    }
    identity_roles = set(identity_user.roles)
    roles = tuple(sorted(registry_roles | identity_roles))
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
    )


def sync_user_with_registry(
    user: AppUser | None,
    settings: PostgresSettings | None,
    auth_provider: str = "streamlit",
    repository_factory=BronzeCatalogRepository,
) -> tuple[AppUser | None, str | None]:
    if user is None:
        return None, None
    if settings is None:
        return user, "Postgres user registry is not configured; using identity roles only."

    try:
        repository = repository_factory(settings)
        repository.initialise()
        registry_row = repository.upsert_app_user_seen(
            user_email=user.email,
            display_name=user.display_name,
            roles=list(user.roles),
            status=initial_registry_status(user),
            auth_provider=auth_provider,
            organisation_id=user.organisation_id,
            organisation_name=user.organisation_name,
        )
    except Exception as exc:
        return user, f"Postgres user registry could not be reached; using identity roles only: {exc}"

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
