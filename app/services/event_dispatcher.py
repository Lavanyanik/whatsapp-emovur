from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.logger import get_logger
from ..handlers.button_handler import WebhookEvent as ButtonWebhookEvent, process_button_reply_event
from ..handlers.interactive_handler import WebhookEvent as InteractiveWebhookEvent, process_interactive_reply_event
from ..handlers.message_handler import WebhookEvent as MessageWebhookEvent, process_incoming_text_event
from ..handlers.status_handler import process_status_event

logger = get_logger(__name__)


async def dispatch(*, event: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    """Dispatch normalized events based on type.

    event contract matches what services.webhook_service.process_event produces.
    """

    message_type = event.get("message_type")
    logger.info("event_dispatcher: dispatching message_type=%s", message_type)

    if message_type == "message":
        ev = MessageWebhookEvent(
            message_id=event.get("message_id"),
            phone=event.get("phone"),
            timestamp=event.get("timestamp"),
            message_type=event.get("message_type"),
            button_title=event.get("button_title"),
            button_payload=event.get("button_payload"),
            button_id=event.get("button_id"),
        )
        return await process_incoming_text_event(event=ev, db=db)

    if message_type == "button":
        ev = ButtonWebhookEvent(
            message_id=event.get("message_id"),
            phone=event.get("phone"),
            timestamp=event.get("timestamp"),
            message_type=event.get("message_type"),
            button_title=event.get("button_title"),
            button_payload=event.get("button_payload"),
            button_id=event.get("button_id"),
        )
        return await process_button_reply_event(event=ev, db=db)

    if message_type == "interactive":
        # Interactive responses for WhatsApp Cloud are handled as button replies.
        ev = InteractiveWebhookEvent(
            message_id=event.get("message_id"),
            phone=event.get("phone"),
            timestamp=event.get("timestamp"),
            message_type=event.get("message_type"),
            button_title=event.get("button_title"),
            # button_payload may contain the button id (normalized upstream)
            button_payload=event.get("button_payload"),
            button_id=event.get("button_id"),
        )
        return await process_interactive_reply_event(event=ev, db=db)


    if message_type == "status":
        return await process_status_event(event=event, db=db)

    logger.info("event_dispatcher: unknown message_type=%s", message_type)
    return {"status": "ignored_unknown_event", "message_type": message_type}

