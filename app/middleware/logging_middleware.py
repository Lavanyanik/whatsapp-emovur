"""HTTP middleware for structured request/response logging.

Logs method, path, status code, and processing time without request bodies.
"""
from time import time

from starlette.types import ASGIApp, Receive, Scope, Send
from ..utils.logger import get_logger

logger = get_logger("middleware.logging")


class LoggingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time()

        try:
            await self.app(scope, receive, send)
        except Exception:
            duration = (time() - start) * 1000
            logger.exception("Request error %s duration=%.2fms", scope.get("method"), duration)
            raise

        duration = (time() - start) * 1000
        # Try to fetch status code from scope (set by Starlette)
        status_code = scope.get("status", "-")

        logger.info("%s status=%s duration=%.2fms", scope.get("method"), status_code, duration)


# For compatibility with FastAPI's add_middleware which expects a class
Middleware = LoggingMiddleware
