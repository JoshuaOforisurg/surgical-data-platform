import pytest

from streamlit_services.tenant_storage import tenant_latest_gold_key, tenant_object_prefix


def test_tenant_keys_are_separated_by_organisation():
    assert tenant_object_prefix("gold/operational/drafts", "hospital-a") == (
        "gold/operational/drafts/hospital-a/"
    )
    assert tenant_latest_gold_key("hospital-a") != tenant_latest_gold_key("hospital-b")


@pytest.mark.parametrize("organisation_id", ["../other", "hospital/a", "", "two words"])
def test_invalid_organisation_id_cannot_escape_tenant_prefix(organisation_id):
    with pytest.raises(ValueError, match="not valid"):
        tenant_object_prefix("gold/operational/drafts", organisation_id)
