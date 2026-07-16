from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.logger import get_logger
from .reply_handler import process_reply_event


logger = get_logger(__name__)


@dataclass(frozen=True)
class WebhookEvent:
    message_id: Optional[str]
    phone: Optional[str]
    timestamp: Optional[Any]
    message_type: str
    button_title: Optional[str] = None
    button_payload: Optional[str] = None
    button_id: Optional[str] = None


async def process_interactive_reply_event(*, event: WebhookEvent, db: AsyncSession) -> Dict[str, Any]:
    logger.info(
        "interactive_handler: received button_title=%s button_payload=%s phone=%s message_id=%s",
        event.button_title,
        event.button_payload,
        event.phone,
        event.message_id,
    )

    return await process_reply_event(
        event=event,
        db=db,
    )


