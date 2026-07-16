"""Async Emovur client service.

Uses httpx to call the exact endpoint and JSON body shown in the provided
Postman collection. Logs request URL, headers (redacts api-key in logs),
payload and response status and body.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import httpx

from ..config import get_settings
from ..constants import DEFAULT_LANGUAGE
from ..utils.logger import get_logger
from ..integrations.whatsapp import get_provider
from .emovur_exceptions import (
    EmovurAuthError,
    EmovurError,
    EmovurRateLimitError,
    EmovurRequestError,
    EmovurServerError,
)
from .template_service import (
    _is_emovur_132001,
    get_template,
    refresh_templates_once_and_get_template,
)

logger = get_logger(__name__)
settings = get_settings()


async def _post_payload(body: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
    url = f"{settings.emovur_api_url.rstrip('/')}/{settings.phone_number_id}/messages"
    headers = {
        "Content-Type": "application/json",
        "api-key": settings.api_key,
    }

    redacted_headers = {k: ("<redacted>" if k.lower() == "api-key" else v) for k, v in headers.items()}
    logger.info("Emovur request URL=%s", url)
    logger.info("Emovur request type=%s to=%s", body.get("type"), body.get("to"))
    logger.debug("Emovur request headers=%s", redacted_headers)
    logger.debug("Emovur request payload=%s", body)

    if getattr(settings, "emovur_dry_run", False):
        logger.info("EMOVUR DRY RUN enabled — simulating send for %s", body.get("to"))
        return {"status_code": 200, "body": {"mock": "message_sent", "to": body.get("to"), "type": body.get("type")}}

    attempt = 0
    max_retries = getattr(settings, "emovur_max_retries", 2)
    backoff_base = getattr(settings, "emovur_backoff_base", 2)

    while True:
        attempt += 1
        timeout_settings = httpx.Timeout(timeout, connect=timeout, read=timeout, write=timeout, pool=timeout)
        async with httpx.AsyncClient(timeout=timeout_settings) as client:
            try:
                logger.info(
                    "Before HTTP request to Emovur attempt=%s timeout=%ss url=%s",
                    attempt,
                    timeout,
                    url,
                )
                logger.debug(
                    "Emovur post headers=%s",
                    {k: ("<redacted>" if k.lower() == "api-key" else v) for k, v in headers.items()},
                )
                logger.debug("Emovur post payload=%s", body)

                try:
                    resp = await client.post(url, headers=headers, json=body)
                except httpx.TimeoutException as exc:
                    # Provide detailed timeout context.
                    logger.exception(
                        "Emovur client.post timed out attempt=%s url=%s to=%s type=%s timeout=%ss exc=%r",
                        attempt,
                        url,
                        body.get("to"),
                        body.get("type"),
                        timeout,
                        exc,
                    )
                    raise

                logger.info(
                    "After HTTP request to Emovur attempt=%s status=%s",
                    attempt,
                    resp.status_code,
                )


                try:
                    content = resp.json()
                except Exception:
                    content = resp.text

                logger.info("Emovur response status=%s", resp.status_code)
                logger.debug("Emovur response body=%s", content)

                if 200 <= resp.status_code < 300:
                    return {"status_code": resp.status_code, "body": content}

                if resp.status_code in (401, 403):
                    raise EmovurAuthError(
                        f"Auth error {resp.status_code}: {content}",
                        status_code=resp.status_code,
                        body=content,
                    )
                if resp.status_code == 429:
                    raise EmovurRateLimitError(
                        f"Rate limited: {content}",
                        status_code=resp.status_code,
                        body=content,
                    )
                if 500 <= resp.status_code < 600:
                    raise EmovurServerError(
                        f"Server error {resp.status_code}: {content}",
                        status_code=resp.status_code,
                        body=content,
                    )

                raise EmovurError(
                    f"Emovur API returned {resp.status_code}: {content}",
                    status_code=resp.status_code,
                    body=content,
                )

            except httpx.TimeoutException as exc:
                logger.exception("Emovur request timed out: %s", exc)
                raise EmovurRequestError("timeout") from exc
            except httpx.RequestError as exc:
                logger.exception("Emovur request error: %s", exc)
                if attempt <= max_retries:
                    wait = backoff_base * (2 ** (attempt - 1))
                    logger.info("Retrying after %s seconds (attempt %s)", wait, attempt)
                    await asyncio.sleep(wait)
                    continue
                raise EmovurRequestError("request_error") from exc


async def send_template(
    to: str,
    template_name: str,
    language: str = DEFAULT_LANGUAGE,
    components: Optional[list] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """Send a template message using Emovur exact POST /{ph-no-id}/messages."""

    resolved = await get_template(template_name, preferred_language=language)
    resolved_name = resolved["template_name"]
    resolved_lang_code = resolved["language_code"]

    body: Dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "template",
        "template": {
            "name": resolved_name,
            "language": {"code": resolved_lang_code},
        },
    }

    if components is not None:
        body["template"]["components"] = components

    logger.info(
        "Outbound template send payload: %s",
        {
            "template_name": template_name,
            "language": language,
            "to": to,
            "body": body,
        },
    )

    try:
        return await _post_payload(body, timeout=timeout)
    except EmovurError as exc:
        if _is_emovur_132001(getattr(exc, "body", None)):
            logger.warning(
                "Emovur template lookup failed (132001). Refreshing templates and retrying once."
            )
            resolved_retry = await refresh_templates_once_and_get_template(
                template_name, preferred_language=language
            )
            body["template"]["name"] = resolved_retry["template_name"]
            body["template"]["language"]["code"] = resolved_retry["language_code"]
            return await _post_payload(body, timeout=timeout)
        raise


async def send_message(payload: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
    """Dispatch any valid WhatsApp message payload to Emovur."""

    if not payload.get("type") or not payload.get("to"):
        raise ValueError("payload must include type and to")
    return await _post_payload(payload, timeout=timeout)


async def send_text(to: str, text: str, timeout: int = 10) -> Dict[str, Any]:
    """Send a plain text message using the Emovur messages endpoint."""

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
    """Send a media message using a media object id."""

    if not media_id:
        raise ValueError("media_id must be provided")

    body: Dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": media_type,
        media_type: {"id": media_id},
    }

    if caption is not None:
        body[media_type]["caption"] = caption

    return await _post_payload(body, timeout=timeout)


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

    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": interactive,
    }

    return await _post_payload(body, timeout=timeout)


# Explicit exports: routes import exception types from this module.
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
    "get_template",
    "refresh_templates_once_and_get_template",
]

