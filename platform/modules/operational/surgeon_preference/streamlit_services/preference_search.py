from __future__ import annotations

import re

import pandas as pd


def filter_preference_cards(
    cards: pd.DataFrame,
    surgeon_query: str = "",
    procedure_query: str = "",
) -> pd.DataFrame:
    """Apply independent, case-insensitive surgeon and procedure filters."""
    filtered = cards.copy()
    for column, query in (
        ("surgeon_name", surgeon_query),
        ("procedure", procedure_query),
    ):
        term = str(query or "").strip()
        if not term:
            continue
        if column not in filtered.columns:
            return filtered.iloc[0:0]
        matches = filtered[column].astype("string").str.contains(
            re.escape(term), case=False, na=False
        )
        filtered = filtered[matches]
    return filtered
