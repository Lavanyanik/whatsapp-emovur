"""Custom exceptions for Emovur client to allow richer error handling."""

class EmovurError(Exception):
    """Base Emovur error."""

    def __init__(self, message: str, status_code: int | None = None, body: object | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class EmovurAuthError(EmovurError):
    """Authentication / authorization error (401/403)."""


class EmovurRateLimitError(EmovurError):
    """Rate limit / throttling error (429)."""


class EmovurServerError(EmovurError):
    """Server-side error (5xx)."""


class EmovurRequestError(EmovurError):
    """Network / request issues (timeouts, connect errors)."""
