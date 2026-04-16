"""Frozen-time helper for demo mode.

When DEMO_FROZEN_TIME is set (ISO 8601, e.g. "2026-04-16T14:26:00Z"),
`now()` returns that instant instead of the real clock. Used to pin the
dashboard to a fixed moment so the site can serve as a static-looking
demo while the ingestion pipeline is shut down.

Unset the env var to return to normal behavior.
"""

import os
from datetime import UTC, datetime
from functools import lru_cache


@lru_cache(maxsize=1)
def _frozen() -> datetime | None:
    raw = os.environ.get("DEMO_FROZEN_TIME", "").strip()
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def now(tz=UTC) -> datetime:
    frozen = _frozen()
    if frozen is not None:
        return frozen.astimezone(tz) if tz else frozen
    return datetime.now(tz)
