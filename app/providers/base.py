"""Shared WhatsApp Cloud API request and payload handling."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import httpx

from ..config import get_settings
from ..constants import DEFAULT_LANGUAGE
from ..services.emovur_exceptions import (
    EmovurAuthError,
    EmovurError,
    EmovurRateLimitError,
    EmovurRequestError,
    EmovurServerError,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class BaseCloudApiProvider:
    """Common implementation for WhatsApp Cloud API-compatible providers."""

    provider_name = "WhatsApp Cloud API"

    def build_request_url(self) -> str:
        raise NotImplementedError

    def build_headers(self) -> Dict[str, str]:
        raise NotImplementedError

    @staticmethod
    def _redact_headers(headers: Dict[str, str]) -> Dict[str, str]:
        sensitive = {"api-key", "authorization"}
        return {key: ("<redacted>" if key.lower() in sensitive else value) for key, value in headers.items()}

    async def _post_payload(self, body: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
        settings = get_settings()
        url = self.build_request_url()
        headers = self.build_headers()
        logger.info("%s request type=%s", self.provider_name, body.get("type"))

        if getattr(settings, "emovur_dry_run", False):
            logger.info("Dry run enabled; simulating send")
            return {"status_code": 200, "body": {"mock": "message_sent", "to": body.get("to"), "type": body.get("type")}}

        max_retries = getattr(settings, "emovur_max_retries", 2)
        backoff_base = getattr(settings, "emovur_backoff_base", 2)
        for attempt in range(1, max_retries + 2):
            try:
                timeout_settings = httpx.Timeout(timeout, connect=timeout, read=timeout, write=timeout, pool=timeout)
                async with httpx.AsyncClient(timeout=timeout_settings) as client:
                    response = await client.post(url, headers=headers, json=body)
                try:
                    content = response.json()
                except ValueError:
                    content = response.text

                if 200 <= response.status_code < 300:
                    return {"status_code": response.status_code, "body": content}
                if response.status_code in (401, 403):
                    raise EmovurAuthError(f"Auth error {response.status_code}: {content}", status_code=response.status_code, body=content)
                if response.status_code == 429:
                    raise EmovurRateLimitError(f"Rate limited: {content}", status_code=response.status_code, body=content)
                if 500 <= response.status_code < 600:
                    raise EmovurServerError(f"Server error {response.status_code}: {content}", status_code=response.status_code, body=content)
                raise EmovurError(f"WhatsApp API returned {response.status_code}: {content}", status_code=response.status_code, body=content)
            except httpx.TimeoutException as exc:
                raise EmovurRequestError("timeout") from exc
            except httpx.RequestError as exc:
                if attempt > max_retries:
                    raise EmovurRequestError("request_error") from exc
                await asyncio.sleep(backoff_base * (2 ** (attempt - 1)))

        raise AssertionError("unreachable")

    async def send_text(self, *, to: str, text: str, timeout: int = 10) -> Dict[str, Any]:
        if not text:
            raise ValueError("text must be provided")
        return await self._post_payload({"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, "type": "text", "text": {"preview_url": False, "body": text}}, timeout)

    async def send_message(self, *, payload: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
        if not payload.get("type") or not payload.get("to"):
            raise ValueError("payload must include type and to")
        return await self._post_payload(payload, timeout)

    async def send_template(self, *, to: str, template_name: str, language: str = DEFAULT_LANGUAGE, components: Optional[list] = None, timeout: int = 10) -> Dict[str, Any]:
        template = await self._resolve_template(template_name, language)
        body: Dict[str, Any] = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, "type": "template", "template": template}
        if components is not None:
            body["template"]["components"] = components
        return await self._send_template_payload(body, template_name, language, timeout)

    async def _resolve_template(self, template_name: str, language: str) -> Dict[str, Any]:
        return {"name": template_name, "language": {"code": language}}

    async def _send_template_payload(self, body: Dict[str, Any], template_name: str, language: str, timeout: int) -> Dict[str, Any]:
        return await self._post_payload(body, timeout)

    async def send_interactive(self, *, to: str, interactive: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
        if not interactive:
            raise ValueError("interactive payload must be provided")
        body = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, "type": "interactive", "interactive": interactive}
        return await self._post_payload(body, timeout)

    async def send_media(self, *, to: str, media_id: str, media_type: str = "image", caption: Optional[str] = None, timeout: int = 10) -> Dict[str, Any]:
        if not media_id:
            raise ValueError("media_id must be provided")
        media: Dict[str, Any] = {"id": media_id}
        if caption is not None:
            media["caption"] = caption
        body = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, "type": media_type, media_type: media}
        return await self._post_payload(body, timeout)

    async def fetch_templates(self, timeout: int = 10) -> list:
        """Default implementation: returns an empty list.
        
        Providers that support template management override this.
        """
        return []

