import pandas as pd

from streamlit_services.demo_data import build_synthetic_demo_cards, filter_demo_cards


def test_demo_cards_are_generated_from_clinical_profiles_without_patient_fields():
    cards = build_synthetic_demo_cards(3)

    assert len(cards) == 3
    assert {
        "surgeon_name",
        "specialty",
        "procedure",
        "instruments",
        "consumables",
        "disposables",
        "implants",
        "special_instructions",
    }.issubset(cards.columns)
    assert not any("patient" in column.lower() for column in cards.columns)
    assert cards["procedure"].notna().all()
    assert all(cards["instruments"].map(bool))


def test_featured_demo_card_shows_full_catalogue_supply_lists_and_workflow_details():
    card = build_synthetic_demo_cards(1).iloc[0]

    assert card["procedure"] == "Total Knee Replacement"
    assert len(card["consumables"]) == 12
    assert len(card["disposables"]) == 4
    assert len(card["draping"]) > 1
    assert card["equipment"]
    assert card["sutures"]
    assert card["dressings"]
    assert card["positioning"]
    assert card["anaesthetic"]
    assert card["skin_prep"]
    assert card["special_instructions"]


def test_demo_card_count_is_bounded():
    assert len(build_synthetic_demo_cards(0)) == 1
    assert len(build_synthetic_demo_cards(101)) == 100


def test_demo_search_matches_surgeon_or_specialty_case_insensitively():
    cards = pd.DataFrame(
        [
            {
                "surgeon_name": "Dr Amina Mensah",
                "specialty": "Orthopaedics",
                "procedure": "Total Hip Replacement (Cemented)",
                "procedure_aliases": ["total hip replacement", "THR", "THA"],
            },
            {
                "surgeon_name": "Dr James Okafor",
                "specialty": "General Surgery",
                "procedure": "Appendicectomy",
                "procedure_aliases": ["appendix removal"],
            },
        ]
    )

    assert filter_demo_cards(cards, "amina")["surgeon_name"].tolist() == [
        "Dr Amina Mensah"
    ]
    assert filter_demo_cards(cards, "ORTHO")["specialty"].tolist() == [
        "Orthopaedics"
    ]
    assert filter_demo_cards(cards, "hip")["procedure"].tolist() == [
        "Total Hip Replacement (Cemented)"
    ]
    assert filter_demo_cards(cards, "THR")["procedure"].tolist() == [
        "Total Hip Replacement (Cemented)"
    ]
    assert filter_demo_cards(cards, "cardiothoracic").empty


def test_featured_card_exposes_aliases_from_the_clinical_reference_catalogue():
    cards = build_synthetic_demo_cards(2)
    knee_card = cards.iloc[0]
    hip_card = cards.iloc[1]

    assert {"tkr", "tka"}.issubset(
        set(alias.lower() for alias in knee_card["procedure_aliases"])
    )
    assert hip_card["procedure"] == "Total Hip Replacement (Cemented)"
    assert {"thr", "tha"}.issubset(
        set(alias.lower() for alias in hip_card["procedure_aliases"])
    )

    by_alias = filter_demo_cards(cards, "THR")
    assert by_alias["procedure"].tolist() == ["Total Hip Replacement (Cemented)"]
