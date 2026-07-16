"""Provider selection for outbound WhatsApp messages."""

from __future__ import annotations

from typing import Optional

from ..config import Settings, get_settings
from .emovur_provider import EmovurProvider
from .meta_provider import MetaProvider
from .protocol import WhatsAppProvider


class ProviderFactory:
    """Create the configured provider, defaulting to direct Meta Cloud API."""

    @staticmethod
    def create(settings: Optional[Settings] = None) -> WhatsAppProvider:
        configured_settings = settings or get_settings()
        provider_name = (getattr(configured_settings, "whatsapp_provider", None) or "").strip().lower()
        if provider_name == "emovur":
            return EmovurProvider()
        return MetaProvider()


def get_provider() -> WhatsAppProvider:
    return ProviderFactory.create()


MetaCloudProvider = MetaProvider
