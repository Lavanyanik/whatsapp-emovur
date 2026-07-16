from __future__ import annotations

from typing import Optional

from ...config import get_settings
from ...providers.emovur_provider import EmovurProvider
from ...providers.factory import MetaCloudProvider
from .base import WhatsAppProvider


def get_provider() -> WhatsAppProvider:
    settings = get_settings()
    provider_name: Optional[str] = getattr(settings, "whatsapp_provider", None)
    if provider_name and str(provider_name).lower() == "emovur":
        return EmovurProvider()
    return MetaCloudProvider()
