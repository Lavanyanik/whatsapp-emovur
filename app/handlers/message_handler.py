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


async def process_incoming_text_event(*, event: WebhookEvent, db: AsyncSession) -> Dict[str, Any]:
    """Process incoming text messages.

    Current backend only supports button/interactive replies for candidate responses,
    so this handler intentionally does minimal work and delegates candidate update
    only if we can interpret the event as a button-like response.
    """

    logger.info("message_handler: received event_type=%s phone=%s message_id=%s", event.message_type, event.phone, event.message_id)

    if not event.phone:
        return {"status": "error_missing_phone"}

    # Reuse same mapping logic as button-based flows.
    return await update_candidate_response_from_button(
        db=db,
        phone=str(event.phone),
        message_id=str(event.message_id) if event.message_id else None,
        button_title=event.button_title,
        button_payload=event.button_payload,
        timestamp=event.timestamp,
    )

