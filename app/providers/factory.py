from __future__ import annotations

from typing import Optional

from ..config import get_settings
from ..utils.logger import get_logger

from .emovur_provider import EmovurProvider
from .base import BaseCloudApiProvider

logger = get_logger(__name__)


def get_provider() -> BaseCloudApiProvider:
    """Return the outbound WhatsApp provider.

    Environment variable selection is provider-agnostic and defaults to the
    Meta-compatible provider when no explicit provider is configured.
    """

    settings = get_settings()
    provider_name: Optional[str] = getattr(settings, "whatsapp_provider", None)

    if provider_name and str(provider_name).lower() == "emovur":
        return EmovurProvider()

    return MetaCloudProvider()


class MetaCloudProvider(EmovurProvider):
    """Fallback provider that preserves the existing outbound contract."""

    def __init__(self) -> None:
        super().__init__()

