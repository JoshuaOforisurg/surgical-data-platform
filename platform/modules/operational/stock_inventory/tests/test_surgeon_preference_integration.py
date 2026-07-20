from __future__ import annotations

import json

import pytest

from integrations.surgeon_preference import load_preference_cards, resolve_preference_requirements


def _preference_card(**overrides):
    card = {
        "surgeon_id": "SURG-001",
        "surgeon_name": "Mr Test",
        "hospital": "Test NHS Trust",
        "procedure": "Total Knee Replacement",
        "procedure_id": "PROC-TKR",
        "procedure_code": "0SRC0JZ",
        "subspecialty": "Joint Replacement",
        "preference_card_uid": "pref-test-tkr",
        "preference_card_version": 3,
        "is_current": True,
        "validation_status": "SUCCESS",
        "instruments_json": json.dumps([{"name": "Large Orthopaedic Set", "quantity": 2}]),
        "consumables_json": json.dumps(
            [
                {"name": "Skin Marker Pen", "quantity": 4},
                {"name": "Uncatalogued Trial Item", "quantity": 1},
            ]
        ),
    }
    card.update(overrides)
    return card


def test_load_preference_cards_keeps_only_current_non_quarantined_rows(tmp_path):
    path = tmp_path / "preference_gold.json"
    path.write_text(
        json.dumps(
            [
                _preference_card(),
                _preference_card(preference_card_uid="old", is_current=False),
                _preference_card(preference_card_uid="quarantined", validation_status="QUARANTINED"),
            ]
        ),
        encoding="utf-8",
    )

    cards = load_preference_cards(path)

    assert [card["preference_card_uid"] for card in cards] == ["pref-test-tkr"]


def test_load_preference_cards_rejects_non_list_payload(tmp_path):
    path = tmp_path / "preference_gold.json"
    path.write_text(json.dumps({"cards": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="JSON list"):
        load_preference_cards(path)


def test_requirement_resolution_keeps_unmatched_items_visible():
    catalogue = [
        {
            "item_id": "INV-INST-LARGE-SET",
            "canonical_name": "Large Orthopaedic Set",
            "item_type": "instrument",
        },
        {
            "item_id": "INV-CONS-MARKER",
            "canonical_name": "Skin Marker Pen",
            "item_type": "consumable",
        },
    ]

    resolution = resolve_preference_requirements([_preference_card()], catalogue)
    requirements = resolution.cards[0]["requirements"]
    unmapped = next(row for row in requirements if row["catalogue_match_status"] == "unmatched")

    assert resolution.card_count == 1
    assert resolution.requirement_count == 3
    assert resolution.matched_requirement_count == 2
    assert resolution.unmatched_requirement_count == 1
    assert unmapped["item_id"].startswith("UNMAPPED-")
    assert unmapped["expected_item_name"] == "Uncatalogued Trial Item"
