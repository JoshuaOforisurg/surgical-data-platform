from __future__ import annotations

import re


def tenant_object_prefix(base_prefix: str, organisation_id: str) -> str:
    tenant_id = str(organisation_id or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", tenant_id):
        raise ValueError("Organisation ID is not valid for tenant object storage.")
    return f"{base_prefix.rstrip('/')}/{tenant_id}/"


def tenant_latest_gold_key(organisation_id: str) -> str:
    prefix = tenant_object_prefix("gold/operational/organisations", organisation_id)
    return f"{prefix}latest/gold_operational_preference_cards.csv"
