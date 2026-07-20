from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ITEM_FIELDS = {
    "instruments_json": "instrument",
    "equipment_json": "equipment",
    "draping_json": "drape",
    "consumables_json": "consumable",
    "disposables_json": "disposable",
    "implants_json": "implant",
    "sutures_json": "suture",
    "dressings_json": "dressing",
}


@dataclass(frozen=True)
class PreferenceRequirementResolution:
    cards: list[dict[str, Any]]
    card_count: int
    requirement_count: int
    matched_requirement_count: int
    unmatched_requirement_count: int

    def summary(self) -> dict[str, int]:
        payload = asdict(self)
        payload.pop("cards")
        return payload


def load_preference_cards(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Surgeon preference Gold must contain a JSON list: {path}")
    if not all(isinstance(row, dict) for row in payload):
        raise ValueError(f"Surgeon preference Gold contains a non-object row: {path}")

    current_cards = [
        row
        for row in payload
        if row.get("is_current") is not False
        and str(row.get("validation_status") or "").upper() != "QUARANTINED"
    ]
    return sorted(
        current_cards,
        key=lambda row: (
            _clean_text(row.get("surgeon_name")).casefold(),
            _clean_text(row.get("procedure") or row.get("procedure_name")).casefold(),
            int(row.get("preference_card_version") or row.get("version_number") or 0),
        ),
    )


def resolve_preference_requirements(
    preference_cards: list[dict[str, Any]],
    catalogue: list[dict[str, Any]],
) -> PreferenceRequirementResolution:
    catalogue_lookup = {
        (str(item.get("item_type") or ""), _normalise_name(item.get("canonical_name"))): str(item["item_id"])
        for item in catalogue
        if item.get("item_id") and item.get("canonical_name") and item.get("item_type")
    }
    resolved_cards = []
    matched_count = 0
    unmatched_count = 0

    for card in preference_cards:
        requirements = []
        for field_name, item_type in ITEM_FIELDS.items():
            for raw_item in _parse_items(card.get(field_name)):
                item_name, quantity = _item_details(raw_item)
                if not item_name:
                    continue
                item_id = catalogue_lookup.get((item_type, _normalise_name(item_name)))
                match_status = "matched" if item_id else "unmatched"
                if item_id:
                    matched_count += 1
                else:
                    unmatched_count += 1
                    item_id = _unmapped_item_id(item_type, item_name)
                requirements.append(
                    {
                        "item_id": item_id,
                        "expected_item_name": item_name,
                        "item_type": item_type,
                        "required_quantity": quantity,
                        "clinical_criticality": _criticality(item_type),
                        "catalogue_match_status": match_status,
                    }
                )

        if not requirements:
            continue
        resolved_cards.append(
            {
                "surgeon_id": _clean_text(card.get("surgeon_id")),
                "surgeon_name": _clean_text(card.get("surgeon_name")) or "Unknown Surgeon",
                "hospital": _clean_text(card.get("hospital")) or "Local NHS Trust",
                "procedure_name": _clean_text(card.get("procedure") or card.get("procedure_name"))
                or "Unknown Procedure",
                "procedure_id": _clean_text(card.get("procedure_id")),
                "procedure_code": _clean_text(card.get("procedure_code") or card.get("opcs_code")),
                "diagnosis_code": _clean_text(card.get("diagnosis_code")),
                "subspecialty": _clean_text(card.get("subspecialty")),
                "preference_card_uid": _preference_card_uid(card),
                "preference_card_version": int(
                    card.get("preference_card_version") or card.get("version_number") or 1
                ),
                "requirements": sorted(
                    requirements,
                    key=lambda row: (row["item_type"], row["expected_item_name"].casefold()),
                ),
            }
        )

    return PreferenceRequirementResolution(
        cards=resolved_cards,
        card_count=len(resolved_cards),
        requirement_count=matched_count + unmatched_count,
        matched_requirement_count=matched_count,
        unmatched_requirement_count=unmatched_count,
    )


def _parse_items(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [part.strip() for part in value.split(",") if part.strip()]
        return parsed if isinstance(parsed, list) else [parsed]
    return [value]


def _item_details(item: Any) -> tuple[str, int]:
    if isinstance(item, dict):
        name = _clean_text(item.get("name") or item.get("item_name"))
        quantity = _positive_int(item.get("quantity"), default=1)
        return name, quantity
    return _clean_text(item), 1


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _criticality(item_type: str) -> str:
    if item_type == "implant":
        return "critical"
    if item_type == "suture":
        return "preference"
    return "required"


def _normalise_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", _clean_text(value)).casefold()
    return "".join(character for character in text if character.isalnum())


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _preference_card_uid(card: dict[str, Any]) -> str:
    existing = _clean_text(card.get("preference_card_uid"))
    if existing:
        return existing
    identity = "|".join(
        [
            _clean_text(card.get("surgeon_id") or card.get("surgeon_name")),
            _clean_text(card.get("procedure_id") or card.get("procedure") or card.get("procedure_name")),
        ]
    ).casefold()
    return f"pref_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]}"


def _unmapped_item_id(item_type: str, item_name: str) -> str:
    digest = hashlib.sha256(f"{item_type}|{_normalise_name(item_name)}".encode("utf-8")).hexdigest()[:16]
    return f"UNMAPPED-{digest.upper()}"
