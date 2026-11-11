from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd

from application_services.contracts import PreferenceCardSearchRequest
from bronze_Ingestion.catalog import BronzeCatalogRepository
from config.settings import PostgresSettings
from streamlit_renderers.preference_card import current_preference_rows
from streamlit_services.preference_card_repository import (
    PreferenceCardRepository,
    current_card_rows_to_dataframe,
)
from streamlit_services.preference_search import filter_preference_cards
from streamlit_services.tenant_access import (
    membership_is_verified,
    scope_snapshot_to_organisation,
)


def load_preference_cards(
    *,
    user: Any,
    organisation_id: str,
    settings: PostgresSettings | None,
    gold_loader: Callable[[], pd.DataFrame | None],
    postgres_loader: Callable[[str], pd.DataFrame | None] | None = None,
    allow_gold_fallback: bool = True,
    membership_repository_factory=BronzeCatalogRepository,
    preference_repository_factory=PreferenceCardRepository,
) -> dict[str, Any]:
    """Authorize the tenant on every call, then load its operational card set."""
    requested_org = str(organisation_id or "").strip()
    if user is None or not requested_org or user.status != "active":
        return _unavailable("An active organisation membership is required.")
    if requested_org != user.organisation_id:
        return _unavailable("The requested organisation does not match your account.")
    if settings is None:
        return _unavailable("The Postgres membership registry is unavailable.")

    try:
        membership_repository = membership_repository_factory(settings)
        membership_repository.initialise()
        membership = membership_repository.get_user_membership(
            user_email=user.email,
            organisation_id=requested_org,
        )
    except Exception:
        return _unavailable("The Postgres membership registry is unavailable.")

    if not membership_is_verified(user, membership):
        return _unavailable("An active membership in this organisation is required.")

    if postgres_loader is not None:
        postgres_df = postgres_loader(requested_org)
    else:
        try:
            rows = preference_repository_factory(settings).list_current_cards(
                organisation_id=requested_org
            )
        except Exception:
            rows = []
        postgres_df = current_card_rows_to_dataframe(rows) if rows else None
    if postgres_df is not None and not postgres_df.empty:
        return {
            "data": postgres_df,
            "source": "Operational database",
            "source_layer": "Postgres",
            "fallback_used": False,
            "message": "Current cards loaded from app_workflow.preference_cards.",
        }

    if not allow_gold_fallback:
        return _unavailable(
            "This organisation has no operational preference cards yet. "
            "A workspace-scoped Gold snapshot is not configured."
        )

    scoped_gold = scope_snapshot_to_organisation(gold_loader(), requested_org)
    if scoped_gold is not None and not scoped_gold.empty:
        return {
            "data": scoped_gold,
            "source": "Gold snapshot fallback",
            "source_layer": "Gold",
            "fallback_used": True,
            "message": "Organisation-scoped cards loaded from the Gold snapshot.",
        }

    return _unavailable(
        "No operational Postgres cards were available. The Gold snapshot is not "
        "organisation-scoped, so it was not used as a tenant fallback."
    )


def search_preference_cards(
    cards: pd.DataFrame,
    surgeon_query: str = "",
    procedure_query: str = "",
) -> pd.DataFrame:
    """Search only the tenant-scoped current-card rows supplied by the caller."""
    request = PreferenceCardSearchRequest(
        surgeon_query=surgeon_query,
        procedure_query=procedure_query,
    )
    return filter_preference_cards(
        current_preference_rows(cards), request.surgeon_query, request.procedure_query
    )


def _unavailable(message: str) -> dict[str, Any]:
    return {
        "data": None,
        "source": "Unavailable",
        "source_layer": "None",
        "fallback_used": True,
        "message": message,
    }
