from __future__ import annotations

import pandas as pd


def membership_is_verified(user, membership: dict | None) -> bool:
    return bool(
        membership
        and user
        and str(membership.get("status") or "").lower() == "active"
        and str(membership.get("organisation_status") or "").lower() == "active"
        and user.status == "active"
        and user.organisation_id == membership.get("organisation_id")
    )


def scope_snapshot_to_organisation(
    snapshot: pd.DataFrame | None,
    organisation_id: str,
) -> pd.DataFrame | None:
    if snapshot is None or snapshot.empty or "organisation_id" not in snapshot.columns:
        return None
    scoped = snapshot[snapshot["organisation_id"].astype(str) == str(organisation_id)]
    return scoped.copy() if not scoped.empty else None
