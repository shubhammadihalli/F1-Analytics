"""Exception hierarchy for the api_clients package."""

from __future__ import annotations

from typing import Any


class APIClientError(Exception):
    """Base class for every error raised by an api_clients client."""


class APIConnectionError(APIClientError):
    """The underlying transport failed (DNS, refused connection, reset, etc.)."""


class APITimeoutError(APIClientError):
    """A request did not complete within the configured timeout."""


class APIAuthenticationError(APIClientError):
    """The remote API rejected the request as unauthenticated/unauthorized (401/403)."""


class APIRateLimitError(APIClientError):
    """The remote API rejected the request as rate limited (429)."""


class APIResponseError(APIClientError):
    """The remote API returned a non-2xx response not covered by a more specific error."""

    def __init__(self, message: str, *, status_code: int, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class UnsupportedEndpointError(APIClientError):
    """The requested operation has no equivalent endpoint on this data provider."""
