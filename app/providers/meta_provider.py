"""Direct Meta WhatsApp Business Cloud API provider."""

from __future__ import annotations

from typing import Dict

from ..config import get_settings
from .base import BaseCloudApiProvider


class MetaProvider(BaseCloudApiProvider):
    """Send messages directly to Meta's WhatsApp Business Cloud API."""

    provider_name = "Meta WhatsApp Cloud API"

    def build_request_url(self) -> str:
        settings = get_settings()
        base_url = settings.meta_api_url or settings.emovur_api_url
        return f"{base_url.rstrip('/')}/{settings.phone_number_id}/messages"

    def build_headers(self) -> Dict[str, str]:
        settings = get_settings()
        token = settings.messages_auth_token or settings.api_key
        return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
