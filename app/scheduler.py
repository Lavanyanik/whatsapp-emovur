"""Scheduler/reminder runtime entrypoint.

Compatibility stub.

The project intentionally removed background scheduler/reminder runtime startup.
However, some external imports (and this repo's tests) expect `app.scheduler` to
remain importable.

This module is therefore a no-op, preserving API compatibility without
reintroducing runtime side-effects.
"""

from __future__ import annotations

from typing import Any


async def start_scheduler(*_args: Any, **_kwargs: Any) -> None:
    """No-op scheduler start.

    Kept to avoid breaking older imports/callers that still attempt to call a
    scheduler start function.
    """

    return None

