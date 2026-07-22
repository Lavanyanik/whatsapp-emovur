"""Provider contract for outbound WhatsApp messages."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class WhatsAppProvider(Protocol):
    """Interface implemented by each outbound WhatsApp provider."""

    async def send_text(self, *, to: str, text: str, timeout: int = 10) -> Dict[str, Any]: ...

    async def send_message(self, *, payload: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]: ...

    async def send_template(
        self,
        *,
        to: str,
        template_name: str,
        language: str,
        components: Optional[list],
        timeout: int,
    ) -> Dict[str, Any]: ...

    async def send_media(
        self,
        *,
        to: str,
        media_id: str,
        media_type: str,
        caption: Optional[str],
        timeout: int,
    ) -> Dict[str, Any]: ...

    async def send_interactive(
        self, *, to: str, interactive: Dict[str, Any], timeout: int = 10
    ) -> Dict[str, Any]: ...

    async def fetch_templates(self, timeout: int = 10) -> List[Dict[str, Any]]:
        """Fetch message templates from the provider.

        Returns a list of template dicts with keys:
          id, name, language, status, category, components
        """
        ...
