from __future__ import annotations

from typing import Any, Dict, Optional

from ..utils.logger import get_logger
from .emovur_service import send_text


logger = get_logger(__name__)


async def send_candidate_response(*, phone: str, text: str, timeout: int = 10) -> Dict[str, Any]:
    """Send the outbound WhatsApp reply for candidate responses.

    IMPORTANT: This reuses the existing Emovur sender implementation.
    """

    logger.info("message_service: sending candidate response to=%s text=%s", phone, text)
    return await send_text(to=phone, text=text, timeout=timeout)

