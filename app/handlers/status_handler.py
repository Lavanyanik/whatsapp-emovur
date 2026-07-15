from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.logger import get_logger

logger = get_logger(__name__)


async def process_status_event(*, event: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    """Process delivery/read/sent statuses.

    Current database model doesn't persist message status events for candidate flow,
    so this handler is a safe no-op placeholder.
    """

    logger.info("status_handler: no-op status event received keys=%s", list(event.keys()) if isinstance(event, dict) else type(event))
    return {"status": "ignored_status_event"}

