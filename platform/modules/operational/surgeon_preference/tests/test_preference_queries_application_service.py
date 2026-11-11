import pandas as pd

from application_services.preference_queries import (
    load_preference_cards,
    search_preference_cards,
)
from streamlit_services.access_control import AppUser


class FakeMembershipRepository:
    def __init__(self, membership=None, error=None):
        self.membership = membership
        self.error = error

    def initialise(self):
        if self.error:
            raise self.error

    def get_user_membership(self, **_kwargs):
        return self.membership


def _user(organisation_id="hospital-a", status="active"):
    return AppUser(
        email="staff@example.com",
        display_name="Theatre Staff",
        roles=("authenticated",),
        status=status,
        organisation_id=organisation_id,
    )


def _membership(organisation_id="hospital-a", status="active", org_status="active"):
    return {
        "organisation_id": organisation_id,
        "status": status,
        "organisation_status": org_status,
    }


def test_load_reads_operational_rows_only_after_live_membership_check():
    calls = []
    postgres_data = pd.DataFrame([{"surgeon_name": "Dr A", "procedure": "Hip"}])
    result = load_preference_cards(
        user=_user(),
        organisation_id="hospital-a",
        settings=object(),
        gold_loader=lambda: calls.append("gold"),
        postgres_loader=lambda org: (calls.append(org), postgres_data)[1],
        membership_repository_factory=lambda _settings: FakeMembershipRepository(
            _membership()
        ),
    )

    assert result["source_layer"] == "Postgres"
    assert result["data"].equals(postgres_data)
    assert calls == ["hospital-a"]


def test_inactive_membership_fails_closed_without_loading_tenant_data():
    calls = []
    result = load_preference_cards(
        user=_user(),
        organisation_id="hospital-a",
        settings=object(),
        gold_loader=lambda: calls.append("gold"),
        postgres_loader=lambda _org: calls.append("postgres"),
        membership_repository_factory=lambda _settings: FakeMembershipRepository(
            _membership(status="suspended")
        ),
    )

    assert result["data"] is None
    assert calls == []


def test_gold_fallback_must_be_scoped_to_the_authorized_organisation():
    gold = pd.DataFrame(
        [
            {"organisation_id": "hospital-a", "surgeon_name": "Dr A"},
            {"organisation_id": "hospital-b", "surgeon_name": "Dr B"},
        ]
    )
    result = load_preference_cards(
        user=_user(),
        organisation_id="hospital-a",
        settings=object(),
        gold_loader=lambda: gold,
        postgres_loader=lambda _org: None,
        membership_repository_factory=lambda _settings: FakeMembershipRepository(
            _membership()
        ),
    )

    assert result["source_layer"] == "Gold"
    assert result["data"]["surgeon_name"].tolist() == ["Dr A"]


def test_new_tenant_does_not_download_global_gold_when_fallback_is_disabled():
    gold_calls = []
    result = load_preference_cards(
        user=_user("hospital-new"),
        organisation_id="hospital-new",
        settings=object(),
        gold_loader=lambda: gold_calls.append(True),
        postgres_loader=lambda _organisation_id: None,
        membership_repository_factory=lambda _settings: FakeMembershipRepository(
            _membership("hospital-new")
        ),
        allow_gold_fallback=False,
    )

    assert result["data"] is None
    assert "no operational preference cards yet" in result["message"]
    assert gold_calls == []


def test_registry_failure_and_unscoped_gold_fail_closed():
    calls = []
    result = load_preference_cards(
        user=_user(),
        organisation_id="hospital-a",
        settings=object(),
        gold_loader=lambda: calls.append("gold"),
        membership_repository_factory=lambda _settings: FakeMembershipRepository(
            error=RuntimeError("database unavailable")
        ),
    )

    assert result["data"] is None
    assert calls == []

    result = load_preference_cards(
        user=_user(),
        organisation_id="hospital-a",
        settings=object(),
        gold_loader=lambda: pd.DataFrame([{"surgeon_name": "Unscoped"}]),
        postgres_loader=lambda _org: None,
        membership_repository_factory=lambda _settings: FakeMembershipRepository(
            _membership()
        ),
    )
    assert result["data"] is None


def test_search_combines_surgeon_and_procedure_on_tenant_current_rows():
    cards = pd.DataFrame(
        [
            {"surgeon_name": "Dr Amina", "procedure": "Total Hip Arthroplasty"},
            {"surgeon_name": "Dr Amina", "procedure": "Total Knee Arthroplasty"},
            {"surgeon_name": "Dr Mensah", "procedure": "Total Hip Arthroplasty"},
        ]
    )

    result = search_preference_cards(cards, "amina", "knee")

    assert result[["surgeon_name", "procedure"]].to_dict("records") == [
        {"surgeon_name": "Dr Amina", "procedure": "Total Knee Arthroplasty"}
    ]
