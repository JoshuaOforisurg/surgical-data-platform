import pytest

from bronze_Ingestion.catalog import assert_active_membership_roles


class Cursor:
    def __init__(self, row):
        self.row = row
        self.query = None

    def execute(self, query, params):
        self.query = (query, params)

    def fetchone(self):
        return self.row


def test_transaction_guard_locks_active_membership_and_checks_role():
    cursor = Cursor({"roles": ["authenticated", "admin"]})

    assert_active_membership_roles(cursor, "Admin@Example.com", "hospital-a", {"admin"})

    query, params = cursor.query
    assert "FOR SHARE OF memberships, organisations" in query
    assert "memberships.status = 'active'" in query
    assert params == ("admin@example.com", "hospital-a")


@pytest.mark.parametrize(
    "row,email,roles",
    [
        (None, "admin@example.com", {"admin"}),
        ({"roles": ["authenticated"]}, "admin@example.com", {"admin"}),
        ({"roles": ["admin"]}, "", {"admin"}),
    ],
)
def test_transaction_guard_rejects_missing_or_insufficient_membership(row, email, roles):
    with pytest.raises(PermissionError):
        assert_active_membership_roles(Cursor(row), email, "hospital-a", roles)
