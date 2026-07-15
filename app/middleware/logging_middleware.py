"""HTTP middleware for structured request/response logging.

Logs method, path, status code, processing time and small JSON bodies with
phone numbers masked. Keeps logging lightweight to avoid impacting throughput.
"""
from time import time
import json
from typing import Callable

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request

from ..utils.logger import get_logger

logger = get_logger("middleware.logging")


def mask_phone(value: str) -> str:
    """Mask a phone number, keeping only last 4 digits for traceability."""
    if not isinstance(value, str) or len(value) == 0:
        return value
    # Keep last 4 characters, mask the rest
    visible = value[-4:]
    return "*" * max(0, len(value) - 4) + visible


class LoggingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        start = time()

        # Read and possibly mask small JSON request bodies
        body_text = ""
        downstream_receive = receive
        try:
            if request.method in ("POST", "PUT", "PATCH"):
                body_bytes = await request.body()
                # Re-inject the body for downstream consumers
                async def _receive() -> dict:
                    nonlocal body_bytes
                    if body_bytes is None:
                        return {"type": "http.request", "body": b"", "more_body": False}

                    chunk = body_bytes
                    body_bytes = None
                    return {"type": "http.request", "body": chunk, "more_body": False}

                downstream_receive = _receive
                request._receive = _receive  # type: ignore[attr-defined]

                if body_bytes and len(body_bytes) < 8192:
                    try:
                        payload = json.loads(body_bytes.decode("utf-8"))
                        # Mask phone if present at top-level
                        if isinstance(payload, dict) and "phone" in payload:
                            payload = dict(payload)
                            payload["phone"] = mask_phone(str(payload.get("phone")))
                        body_text = json.dumps(payload)
                    except Exception:
                        body_text = "<non-json or too large>"
        except Exception:
            # Don't let logging errors block request processing
            logger.exception("Failed to read request body for logging")

        try:
            await self.app(scope, downstream_receive, send)
        except Exception:
            duration = (time() - start) * 1000
            logger.exception("Request error %s %s duration=%.2fms body=%s", request.method, request.url.path, duration, body_text)
            raise

        duration = (time() - start) * 1000
        # Try to fetch status code from scope (set by Starlette)
        status_code = scope.get("status", "-")

        logger.info("%s %s status=%s duration=%.2fms body=%s", request.method, request.url.path, status_code, duration, body_text)


# For compatibility with FastAPI's add_middleware which expects a class
Middleware = LoggingMiddleware
