"""Dispatch normalized webhook events to their registered handlers."""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from ..handlers.button_handler import process_button_reply_event
from ..utils.logger import get_logger

logger = get_logger(__name__)


async def dispatch_event(*, event: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    """Route button and interactive replies through the candidate handler."""
    message_type = event.get("message_type")
    logger.info("event_dispatcher: dispatching message_type=%s", message_type)
    if message_type in {"button", "interactive"}:
        return await process_button_reply_event(event=event, db=db)
    logger.info("event_dispatcher: ignored message_type=%s", message_type)
    return {"status": "ignored_unknown_event", "message_type": message_type}


dispatch = dispatch_event
