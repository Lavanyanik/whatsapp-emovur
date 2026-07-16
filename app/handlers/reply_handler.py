from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.logger import get_logger
from ..services.candidate_service import update_candidate_response_from_button

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


async def process_reply_event(*, event: WebhookEvent, db: AsyncSession) -> Dict[str, Any]:
    """Shared reply handler.

    This module centralizes the identical business logic that was previously
    duplicated across message/button/interactive handlers.

    Public behavior is preserved:
      - if phone is missing, returns {"status": "error_missing_phone"}
      - otherwise delegates to update_candidate_response_from_button(...)
    """

    # Keep the same missing-phone contract used by the old handlers.
    if not event.phone:
        return {"status": "error_missing_phone"}

    return await update_candidate_response_from_button(
        db=db,
        phone=str(event.phone),
        message_id=str(event.message_id) if event.message_id else None,
        button_title=event.button_title,
        button_payload=event.button_payload,
        timestamp=event.timestamp,
    )

