"""Direct Meta WhatsApp Business Cloud API provider."""

from __future__ import annotations

from typing import Any, Dict, List

import httpx

from ..config import get_settings
from ..utils.logger import get_logger
from .base import BaseCloudApiProvider

logger = get_logger(__name__)


class MetaProvider(BaseCloudApiProvider):
    """Send messages directly to Meta's WhatsApp Business Cloud API."""

    provider_name = "Meta WhatsApp Cloud API"

    def build_request_url(self) -> str:
        settings = get_settings()
        phone_number_id = settings.whatsapp_phone_number_id or settings.phone_number_id
        return f"https://graph.facebook.com/{settings.graph_api_version}/{phone_number_id}/messages"

    def build_headers(self) -> Dict[str, str]:
        settings = get_settings()
        token = settings.whatsapp_access_token or settings.messages_auth_token
        return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    async def fetch_templates(self, timeout: int = 10) -> List[Dict[str, Any]]:
        """Fetch WhatsApp message templates from Meta Graph API.

        Uses the WhatsApp Business Account ID to call:
          GET /{{graph-api-version}}/{{waba-id}}/message_templates
        """
        settings = get_settings()
        waba_id = settings.whatsapp_business_account_id or settings.waba_id
        if not waba_id:
            logger.warning("MetaProvider: no WABA ID configured for template fetch")
            return []

        url = f"https://graph.facebook.com/{settings.graph_api_version}/{waba_id}/message_templates"
        headers = self.build_headers()

        logger.info("Fetching Meta templates URL=%s", url)

        timeout_settings = httpx.Timeout(timeout, connect=timeout, read=timeout, write=timeout, pool=timeout)
        async with httpx.AsyncClient(timeout=timeout_settings) as client:
            resp = await client.get(url, headers=headers)
            try:
                content = resp.json()
            except Exception:
                content = resp.text

        if not (200 <= resp.status_code < 300):
            logger.error("Failed to fetch Meta templates: status=%s body=%s", resp.status_code, content)
            return []

        data = content.get("data") if isinstance(content, dict) else content
        if not isinstance(data, list):
            return []

        records: List[Dict[str, Any]] = []
        for t in data:
            if not isinstance(t, dict):
                continue
            tid = t.get("id") or t.get("template_id") or ""
            name = t.get("name") or t.get("template_name") or ""
            status = t.get("status") or ""
            category = t.get("category")
            components = t.get("components")
            language = ""
            if isinstance(t.get("language"), dict):
                language = str(t["language"].get("code", ""))
            elif isinstance(t.get("language"), str):
                language = t["language"]

            if not tid or not name:
                continue

            records.append({
                "id": str(tid),
                "name": str(name),
                "language": language,
                "status": str(status),
                "category": str(category) if category is not None else None,
                "components": components,
            })

        return records
