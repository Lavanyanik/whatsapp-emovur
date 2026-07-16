"""Async Emovur client service.

Uses the configured WhatsApp provider to dispatch outbound messages while
preserving the existing request payload contract.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..constants import DEFAULT_LANGUAGE
from ..providers import get_provider
from ..utils.logger import get_logger
from .emovur_exceptions import (
    EmovurAuthError,
    EmovurError,
    EmovurRateLimitError,
    EmovurRequestError,
    EmovurServerError,
)

logger = get_logger(__name__)


async def send_template(
    to: str,
    template_name: str,
    language: str = DEFAULT_LANGUAGE,
    components: Optional[list] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """Send a template message via the configured provider."""
    provider = get_provider()
    return await provider.send_template(
        to=to,
        template_name=template_name,
        language=language,
        components=components,
        timeout=timeout,
    )


async def send_message(payload: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
    """Dispatch any valid WhatsApp message payload via the configured provider."""
    if not payload.get("type") or not payload.get("to"):
        raise ValueError("payload must include type and to")
    provider = get_provider()
    return await provider.send_message(payload=payload, timeout=timeout)


async def send_text(to: str, text: str, timeout: int = 10) -> Dict[str, Any]:
    """Send a plain text message via the configured provider."""
    if not text:
        raise ValueError("text must be provided")
    provider = get_provider()
    return await provider.send_text(to=to, text=text, timeout=timeout)


async def send_media(
    to: str,
    media_id: str,
    media_type: str = "image",
    caption: Optional[str] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """Send a media message via the configured provider."""
    if not media_id:
        raise ValueError("media_id must be provided")
    provider = get_provider()
    return await provider.send_media(
        to=to,
        media_id=media_id,
        media_type=media_type,
        caption=caption,
        timeout=timeout,
    )


async def send_image(to: str, media_id: str, caption: Optional[str] = None, timeout: int = 10) -> Dict[str, Any]:
    return await send_media(to=to, media_id=media_id, media_type="image", caption=caption, timeout=timeout)


async def send_document(to: str, media_id: str, caption: Optional[str] = None, timeout: int = 10) -> Dict[str, Any]:
    return await send_media(to=to, media_id=media_id, media_type="document", caption=caption, timeout=timeout)


async def send_video(to: str, media_id: str, caption: Optional[str] = None, timeout: int = 10) -> Dict[str, Any]:
    return await send_media(to=to, media_id=media_id, media_type="video", caption=caption, timeout=timeout)


async def send_audio(to: str, media_id: str, timeout: int = 10) -> Dict[str, Any]:
    return await send_media(to=to, media_id=media_id, media_type="audio", timeout=timeout)


async def send_interactive(
    to: str,
    interactive: Dict[str, Any],
    timeout: int = 10,
) -> Dict[str, Any]:
    if not interactive:
        raise ValueError("interactive payload must be provided")
    provider = get_provider()
    return await provider.send_interactive(to=to, interactive=interactive, timeout=timeout)


__all__ = [
    "EmovurAuthError",
    "EmovurError",
    "EmovurRateLimitError",
    "EmovurRequestError",
    "EmovurServerError",
    "send_template",
    "send_message",
    "send_text",
    "send_image",
    "send_document",
    "send_video",
    "send_audio",
    "send_interactive",
]

