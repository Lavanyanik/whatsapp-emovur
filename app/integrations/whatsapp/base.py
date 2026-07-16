from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class WhatsAppProvider(Protocol):
    async def send_text(self, *, to: str, text: str, timeout: int = 10) -> Dict[str, Any]:
        ...

    async def send_template(
        self,
        *,
        to: str,
        template_name: str,
        language: str,
        components: Optional[list],
        timeout: int,
    ) -> Dict[str, Any]:
        ...

    async def send_media(
        self,
        *,
        to: str,
        media_id: str,
        media_type: str,
        caption: Optional[str],
        timeout: int,
    ) -> Dict[str, Any]:
        ...

    async def send_interactive(self, *, to: str, interactive: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
        ...
