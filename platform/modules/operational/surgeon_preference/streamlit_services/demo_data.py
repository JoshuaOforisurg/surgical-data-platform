from __future__ import annotations

import re

import pandas as pd

from domain.clinical_reference_service import ClinicalReferenceService
from generate_synthetic_data.main_synthetic_generator import generate_single_card
from generate_synthetic_data import shared_catalogue


def _generated_card_row(card) -> dict:
    clinical_reference = ClinicalReferenceService()
    procedure_id = clinical_reference.resolve_procedure(card.procedure.name)
    procedure_reference = next(
        (
            item
            for item in clinical_reference.procedure_table()
            if item.procedure_id == procedure_id
        ),
        None,
    )
    instructions = clinical_reference.instructions_for_procedure(procedure_id)
    return {
        "surgeon_name": card.surgeon.full_name,
        "specialty": card.specialty,
        "procedure": card.procedure.name,
        "procedure_aliases": procedure_reference.aliases if procedure_reference else [],
        "instrument_system": shared_catalogue.CLINICAL_PREFERENCE_PROFILES[
            card.procedure.name
        ].get("instrument_system", ""),
        "implant_system": shared_catalogue.CLINICAL_PREFERENCE_PROFILES[
            card.procedure.name
        ].get("implant_system", ""),
        "instruments": [
            {"name": item.name, "quantity": item.quantity}
            for item in card.instruments or []
        ],
        "equipment": [item.name for item in card.equipment or []],
        "draping": [item.name for item in card.draping or []],
        "consumables": [item.name for item in card.consumables or []],
        "disposables": [item.name for item in card.disposables or []],
        "implants": [item.name for item in card.implants or []],
        "sutures": [item.name for item in card.sutures or []],
        "dressings": [item.name for item in card.dressings or []],
        "positioning": card.positioning.description if card.positioning else "",
        "anaesthetic": card.anaesthetic.notes if card.anaesthetic else "",
        "skin_prep": card.skin_prep.description if card.skin_prep else "",
        "special_instructions": instructions,
    }


def _featured_profile_row(
    procedure_name: str = "Total Knee Replacement",
    surgeon_name: str = "Mr Patel",
) -> dict:
    profile = shared_catalogue.CLINICAL_PREFERENCE_PROFILES[procedure_name]
    procedure_data = next(
        procedure
        for subspecialty in shared_catalogue.SUBSPECIALTIES["Orthopaedics"]
        for procedure in shared_catalogue.PROCEDURES[subspecialty]
        if procedure["name"] == procedure_name
    )
    clinical_reference = ClinicalReferenceService()
    procedure_id = clinical_reference.resolve_procedure(procedure_name)
    draping = [profile.get("drape_pack", ""), *profile.get("draping_order", [])]

    return {
        "surgeon_name": surgeon_name,
        "specialty": "Orthopaedics",
        "procedure": procedure_name,
        "procedure_aliases": next(
            (
                item.aliases
                for item in clinical_reference.procedure_table()
                if item.procedure_id == procedure_id
            ),
            [],
        ),
        "instrument_system": profile.get("instrument_system", ""),
        "implant_system": profile.get("implant_system", ""),
        "instruments": profile.get("instruments", []),
        "equipment": profile.get("equipment", []),
        "draping": list(dict.fromkeys(item for item in draping if item)),
        "consumables": profile.get("consumables", []),
        "disposables": profile.get("disposables", []),
        "implants": profile.get("implants") or [],
        "sutures": profile.get("sutures", []),
        "dressings": profile.get("dressings", []),
        "positioning": profile.get("positioning", ""),
        "anaesthetic": profile.get("anaesthetic", ""),
        "skin_prep": profile.get("skin_prep", ""),
        "special_instructions": clinical_reference.instructions_for_procedure(
            procedure_id
        ),
        "procedure_codes": procedure_data.get("codes", {}).get("procedure", []),
    }


def build_synthetic_demo_cards(count: int = 16) -> pd.DataFrame:
    """Build a read-only, patient-free demo from the project's clinical profiles."""
    card_count = max(1, min(count, 100))
    rows = [_featured_profile_row()]
    if card_count > 1:
        rows.append(
            _featured_profile_row(
                "Total Hip Replacement (Cemented)",
                surgeon_name="Mr Mensah",
            )
        )
    for _ in range(card_count - len(rows)):
        card = generate_single_card(export=False, messy=False)
        rows.append(_generated_card_row(card))
    return pd.DataFrame(rows)


def filter_demo_cards(cards: pd.DataFrame, query: str = "") -> pd.DataFrame:
    """Search demo cards by surgeon, specialty, procedure, or procedure alias."""
    term = str(query or "").strip()
    if not term or cards is None or cards.empty:
        return cards.copy() if cards is not None else pd.DataFrame()

    searchable = [
        column
        for column in ("surgeon_name", "specialty", "procedure", "procedure_aliases")
        if column in cards
    ]
    if not searchable:
        return cards.iloc[0:0].copy()

    matches = pd.Series(False, index=cards.index)

    def searchable_text(value) -> str:
        if isinstance(value, (list, tuple, set)):
            return " ".join(str(item) for item in value)
        if value is None or pd.isna(value):
            return ""
        return str(value)

    def contains_query(value: str) -> bool:
        folded = value.casefold()
        if len(term) <= 3:
            return any(
                token.startswith(term.casefold())
                for token in re.findall(r"[a-z0-9]+", folded)
            )
        return term.casefold() in folded

    for column in searchable:
        if column == "procedure_aliases":
            def alias_matches(value) -> bool:
                aliases = value if isinstance(value, (list, tuple, set)) else [value]
                for alias in aliases:
                    alias_text = str(alias or "").casefold()
                    if len(term) <= 3:
                        if any(
                            token.startswith(term.casefold())
                            for token in re.findall(r"[a-z0-9]+", alias_text)
                        ):
                            return True
                    elif term.casefold() in alias_text:
                        return True
                return False

            matches |= cards[column].map(alias_matches)
            continue

        values = cards[column].map(searchable_text)
        matches |= values.map(contains_query)
    return cards[matches].copy()
