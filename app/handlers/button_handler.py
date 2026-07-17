"""Handler for normalized WhatsApp button replies."""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from ..services.candidate_service import update_candidate_response
from ..utils.logger import get_logger

logger = get_logger(__name__)


async def process_button_reply_event(*, event: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    logger.info(
        "button_handler: received phone=%s message_id=%s",
        event.get("phone"),
        event.get("message_id"),
    )
    phone = event.get("phone")
    if not phone:
        return {"status": "error_missing_phone"}
    return await update_candidate_response(
        db=db,
        phone=str(phone),
        message_id=event.get("message_id"),
        button_title=event.get("button_title"),
        button_payload=event.get("button_payload"),
        timestamp=event.get("timestamp"),
    )
