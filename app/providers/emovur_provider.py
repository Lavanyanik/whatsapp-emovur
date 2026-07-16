"""Emovur WhatsApp Cloud API provider."""

from __future__ import annotations

from typing import Any, Dict

from ..config import get_settings
from ..services.emovur_exceptions import EmovurError
from ..services.template_service import _is_emovur_132001, get_template, refresh_templates_once_and_get_template
from .base import BaseCloudApiProvider


class EmovurProvider(BaseCloudApiProvider):
    provider_name = "Emovur"

    def build_request_url(self) -> str:
        settings = get_settings()
        return f"{settings.emovur_api_url.rstrip('/')}/{settings.phone_number_id}/messages"

    def build_headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json", "api-key": get_settings().api_key}

    async def _resolve_template(self, template_name: str, language: str) -> Dict[str, Any]:
        resolved = await get_template(template_name, preferred_language=language)
        return {"name": resolved["template_name"], "language": {"code": resolved["language_code"]}}

    async def _send_template_payload(self, body: Dict[str, Any], template_name: str, language: str, timeout: int) -> Dict[str, Any]:
        try:
            return await self._post_payload(body, timeout)
        except EmovurError as exc:
            if not _is_emovur_132001(getattr(exc, "body", None)):
                raise
            resolved = await refresh_templates_once_and_get_template(template_name, preferred_language=language)
            body["template"]["name"] = resolved["template_name"]
            body["template"]["language"]["code"] = resolved["language_code"]
            return await self._post_payload(body, timeout)
