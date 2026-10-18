import pandas as pd

from streamlit_services.access_control import AppUser
from streamlit_services.tenant_access import membership_is_verified, scope_snapshot_to_organisation


def test_only_matching_active_membership_authorizes_tenant_data():
    user = AppUser(
        email="person@example.com",
        display_name="Person",
        roles=("authenticated", "editor"),
        status="active",
        organisation_id="hospital-a",
    )
    membership = {
        "organisation_id": "hospital-a",
        "organisation_status": "active",
        "status": "active",
    }

    assert membership_is_verified(user, membership)
    assert not membership_is_verified(user, {**membership, "organisation_id": "hospital-b"})
    assert not membership_is_verified(user, {**membership, "status": "suspended"})
    assert not membership_is_verified(user, {**membership, "organisation_status": "suspended"})


def test_gold_fallback_requires_and_filters_organisation_id():
    snapshot = pd.DataFrame(
        [
            {"organisation_id": "hospital-a", "surgeon_name": "Surgeon A"},
            {"organisation_id": "hospital-b", "surgeon_name": "Surgeon B"},
        ]
    )

    scoped = scope_snapshot_to_organisation(snapshot, "hospital-a")

    assert scoped["surgeon_name"].tolist() == ["Surgeon A"]
    assert scope_snapshot_to_organisation(snapshot.drop(columns="organisation_id"), "hospital-a") is None
    assert scope_snapshot_to_organisation(snapshot, "hospital-c") is None
