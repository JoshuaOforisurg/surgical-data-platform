from datetime import UTC, datetime, timedelta, timezone

import pytest

from orchestration.run_identity import new_run_id


def test_run_id_is_readable_and_collision_resistant():
    started_at = datetime(2026, 8, 17, 14, 5, 9, 123456, tzinfo=UTC)

    run_id = new_run_id(started_at=started_at, entropy="a1b2c3d4")

    assert run_id == "run_20260817_140509_123456_a1b2c3d4"


def test_run_id_normalises_time_to_utc():
    british_summer_time = timezone(timedelta(hours=1))
    started_at = datetime(2026, 8, 17, 15, 5, 9, 123456, tzinfo=british_summer_time)

    run_id = new_run_id(started_at=started_at, entropy="a1b2c3d4")

    assert run_id == "run_20260817_140509_123456_a1b2c3d4"


def test_run_id_rejects_unsafe_entropy():
    with pytest.raises(ValueError, match="entropy"):
        new_run_id(entropy="bad/path")
