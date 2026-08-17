from __future__ import annotations

import uuid
from datetime import UTC, datetime


def new_run_id(
    *,
    started_at: datetime | None = None,
    entropy: str | None = None,
) -> str:
    """Create a readable, collision-resistant identity for one pipeline run."""

    timestamp = started_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    else:
        timestamp = timestamp.astimezone(UTC)

    suffix = (entropy or uuid.uuid4().hex[:8]).strip().lower()
    if len(suffix) < 8 or not suffix.isalnum():
        raise ValueError("run id entropy must contain at least 8 letters or digits")

    return f"run_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}_{suffix}"
