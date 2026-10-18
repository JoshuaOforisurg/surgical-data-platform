import pandas as pd
import pytest

from streamlit_services.preference_search import filter_preference_cards


@pytest.fixture
def cards():
    return pd.DataFrame(
        [
            {"surgeon_name": "Dr Amina Clarke", "procedure": "Total Hip Replacement"},
            {"surgeon_name": "Dr Amina Clarke", "procedure": "Total Knee Replacement"},
            {"surgeon_name": "Mr Daniel Mensah", "procedure": "Total Hip Replacement"},
        ]
    )


def test_combined_search_requires_surgeon_and_procedure_to_match(cards):
    result = filter_preference_cards(cards, "amina", "knee")

    assert result[["surgeon_name", "procedure"]].to_dict("records") == [
        {"surgeon_name": "Dr Amina Clarke", "procedure": "Total Knee Replacement"}
    ]


def test_either_filter_can_be_used_independently(cards):
    by_surgeon = filter_preference_cards(cards, surgeon_query="amina")
    by_procedure = filter_preference_cards(cards, procedure_query="hip")

    assert len(by_surgeon) == 2
    assert len(by_procedure) == 2


def test_blank_search_returns_all_cards(cards):
    assert len(filter_preference_cards(cards)) == len(cards)


def test_search_treats_regex_characters_as_literal(cards):
    result = filter_preference_cards(cards, surgeon_query="Amina[")

    assert result.empty
