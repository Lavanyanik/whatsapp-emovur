from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from ..config import get_settings
from ..utils.logger import get_logger
from ..services.emovur_exceptions import (
    EmovurAuthError,
    EmovurError,
    EmovurRateLimitError,
    EmovurRequestError,
    EmovurServerError,
)


logger = get_logger(__name__)
settings = get_settings()


@dataclass(frozen=True)
class BaseCloudApiProvider:
    """Base class responsible for request/retry/backoff/timeout behavior.

    Concrete providers override:
      - build_request_url(...)
      - build_headers(...)

    Notes:
      - This is intentionally minimal so we preserve existing payloads and
        error/exception behavior from the legacy emovur_service implementation.
    """

    def build_request_url(self) -> str:
        raise NotImplementedError

    def build_headers(self) -> Dict[str, str]:
        raise NotImplementedError

    def _redact_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        return {k: ("<redacted>" if k.lower() == "api-key" else v) for k, v in headers.items()}

    async def _post_payload(self, body: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
        url = self.build_request_url()
        headers = self.build_headers()

        redacted_headers = self._redact_headers(headers)
        logger.info("Emovur request URL=%s", url)
        logger.info("Emovur request type=%s to=%s", body.get("type"), body.get("to"))
        logger.debug("Emovur request headers=%s", redacted_headers)
        logger.debug("Emovur request payload=%s", body)

        if getattr(settings, "emovur_dry_run", False):
            logger.info("EMOVUR DRY RUN enabled — simulating send for %s", body.get("to"))
            return {
                "status_code": 200,
                "body": {"mock": "message_sent", "to": body.get("to"), "type": body.get("type")},
            }

        attempt = 0
        max_retries = getattr(settings, "emovur_max_retries", 2)
        backoff_base = getattr(settings, "emovur_backoff_base", 2)

        while True:
            attempt += 1
            timeout_settings = httpx.Timeout(timeout, connect=timeout, read=timeout, write=timeout, pool=timeout)
            async with httpx.AsyncClient(timeout=timeout_settings) as client:
                try:
                    logger.info(
                        "Before HTTP request to Emovur attempt=%s timeout=%ss url=%s",
                        attempt,
                        timeout,
                        url,
                    )
                    logger.debug(
                        "Emovur post headers=%s",
                        {k: ("<redacted>" if k.lower() == "api-key" else v) for k, v in headers.items()},
                    )
                    logger.debug("Emovur post payload=%s", body)

                    try:
                        resp = await client.post(url, headers=headers, json=body)
                    except httpx.TimeoutException as exc:
                        logger.exception(
                            "Emovur client.post timed out attempt=%s url=%s to=%s type=%s timeout=%ss exc=%r",
                            attempt,
                            url,
                            body.get("to"),
                            body.get("type"),
                            timeout,
                            exc,
                        )
                        raise

                    logger.info(
                        "After HTTP request to Emovur attempt=%s status=%s",
                        attempt,
                        resp.status_code,
                    )

                    try:
                        content = resp.json()
                    except Exception:
                        content = resp.text

                    logger.info("Emovur response status=%s", resp.status_code)
                    logger.debug("Emovur response body=%s", content)

                    if 200 <= resp.status_code < 300:
                        return {"status_code": resp.status_code, "body": content}

                    if resp.status_code in (401, 403):
                        raise EmovurAuthError(
                            f"Auth error {resp.status_code}: {content}",
                            status_code=resp.status_code,
                            body=content,
                        )
                    if resp.status_code == 429:
                        raise EmovurRateLimitError(
                            f"Rate limited: {content}",
                            status_code=resp.status_code,
                            body=content,
                        )
                    if 500 <= resp.status_code < 600:
                        raise EmovurServerError(
                            f"Server error {resp.status_code}: {content}",
                            status_code=resp.status_code,
                            body=content,
                        )

                    raise EmovurError(
                        f"Emovur API returned {resp.status_code}: {content}",
                        status_code=resp.status_code,
                        body=content,
                    )

                except httpx.TimeoutException as exc:
                    logger.exception("Emovur request timed out: %s", exc)
                    raise EmovurRequestError("timeout") from exc
                except httpx.RequestError as exc:
                    logger.exception("Emovur request error: %s", exc)
                    if attempt <= max_retries:
                        wait = backoff_base * (2 ** (attempt - 1))
                        logger.info("Retrying after %s seconds (attempt %s)", wait, attempt)
                        await asyncio.sleep(wait)
                        continue
                    raise EmovurRequestError("request_error") from exc

    # --- Abstract send APIs ---
    async def send_text(self, *, to: str, text: str, timeout: int = 10) -> Dict[str, Any]:
        raise NotImplementedError

    async def send_template(
        self,
        *,
        to: str,
        template_name: str,
        language: str,
        components: Optional[list],
        timeout: int,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    async def send_media(
        self,
        *,
        to: str,
        media_id: str,
        media_type: str,
        caption: Optional[str],
        timeout: int,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    async def send_interactive(self, *, to: str, interactive: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
        raise NotImplementedError

