from __future__ import annotations

import re
from functools import lru_cache

import pandas as pd

from domain.clinical_reference_service import ClinicalReferenceService


def _normalise_alias(value: str) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


@lru_cache(maxsize=256)
def _exact_alias_procedure_id(value: str) -> str | None:
    query = _normalise_alias(value)
    for procedure in ClinicalReferenceService().procedure_table():
        if query and query in {_normalise_alias(alias) for alias in procedure.aliases}:
            return procedure.procedure_id
    return None

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
        pattern = re.escape(term)
        if column == "procedure" and len(term) <= 3:
            pattern = rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])"
        matches = filtered[column].astype("string").str.contains(
            pattern,
            case=False,
            na=False,
            regex=True,
        )
        if column == "procedure":
            procedure_id = _exact_alias_procedure_id(term)
            if procedure_id:
                procedure = next(
                    item
                    for item in ClinicalReferenceService().procedure_table()
                    if item.procedure_id == procedure_id
                )
                known_names = {
                    _normalise_alias(name)
                    for name in (procedure.name, *procedure.aliases)
                }
                if "procedure_id" in filtered.columns:
                    matches |= filtered["procedure_id"].astype("string").eq(procedure_id)
                row_names = filtered[column].map(
                    lambda value: _normalise_alias(value) if pd.notna(value) else ""
                )
                matches |= row_names.isin(known_names)
        filtered = filtered[matches]
    return filtered
