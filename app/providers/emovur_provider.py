"""Emovur WhatsApp Cloud API provider."""

from __future__ import annotations

from typing import Any, Dict, List

import httpx

from ..config import get_settings
from ..services.emovur_exceptions import EmovurError
from ..utils.logger import get_logger
from .base import BaseCloudApiProvider

logger = get_logger(__name__)


def _extract_language_code(template_obj: Dict[str, Any]) -> str:
    lang = template_obj.get("language")
    if isinstance(lang, dict):
        code = lang.get("code")
        if code:
            return str(code)
    if isinstance(lang, str):
        return lang
    code = template_obj.get("language_code")
    if code:
        return str(code)
    return ""


def _parse_templates_from_emovur(payload: Any) -> List[Dict[str, Any]]:
    raw_list: Any = payload
    if isinstance(payload, dict):
        for key in ("data", "templates", "message_templates", "results"):
            if key in payload and isinstance(payload[key], list):
                raw_list = payload[key]
                break

    if not isinstance(raw_list, list):
        return []

    records: List[Dict[str, Any]] = []
    for t in raw_list:
        if not isinstance(t, dict):
            continue
        tid = t.get("id") or t.get("template_id") or ""
        name = t.get("name") or t.get("template_name") or ""
        status = t.get("status") or ""
        category = t.get("category")
        components = t.get("components")
        language = _extract_language_code(t)

        if not tid or not name:
            continue

        records.append({
            "id": str(tid),
            "name": str(name),
            "language": str(language),
            "status": str(status),
            "category": str(category) if category is not None else None,
            "components": components,
        })

    return records


class EmovurProvider(BaseCloudApiProvider):
    provider_name = "Emovur"

    def build_request_url(self) -> str:
        settings = get_settings()
        return f"{settings.emovur_api_url.rstrip('/')}/{settings.phone_number_id}/messages"

    def build_headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json", "api-key": get_settings().api_key}

    async def _resolve_template(self, template_name: str, language: str) -> Dict[str, Any]:
        from ..services.template_service import get_template
        resolved = await get_template(template_name, preferred_language=language)
        return {"name": resolved["template_name"], "language": {"code": resolved["language_code"]}}

    async def _send_template_payload(self, body: Dict[str, Any], template_name: str, language: str, timeout: int) -> Dict[str, Any]:
        from ..services.template_service import _is_emovur_132001, refresh_templates_once_and_get_template
        try:
            return await self._post_payload(body, timeout)
        except EmovurError as exc:
            if not _is_emovur_132001(getattr(exc, "body", None)):
                raise
            resolved = await refresh_templates_once_and_get_template(template_name, preferred_language=language)
            body["template"]["name"] = resolved["template_name"]
            body["template"]["language"]["code"] = resolved["language_code"]
            return await self._post_payload(body, timeout)

    async def fetch_templates(self, timeout: int = 10) -> List[Dict[str, Any]]:
        """Fetch templates from Emovur API."""
        settings = get_settings()
        url = f"{settings.emovur_api_url.rstrip('/')}/{settings.waba_id}/message_templates"
        headers = {
            "Content-Type": "application/json",
            "api-key": settings.api_key,
        }

        if getattr(settings, "emovur_dry_run", False):
            logger.info("EMOVUR DRY RUN enabled — returning empty template cache")
            return []

        logger.info("Fetching Emovur templates URL=%s", url)

        timeout_settings = httpx.Timeout(timeout, connect=timeout, read=timeout, write=timeout, pool=timeout)
        async with httpx.AsyncClient(timeout=timeout_settings) as client:
            resp = await client.get(url, headers=headers)
            try:
                content = resp.json()
            except Exception:
                content = resp.text

        if not (200 <= resp.status_code < 300):
            logger.error("Failed to fetch Emovur templates: status=%s body=%s", resp.status_code, content)
            return []

        return _parse_templates_from_emovur(content)
