"""Unit tests for the api_clients exception hierarchy."""

from __future__ import annotations

import pytest

from api_clients.exceptions import (
    APIAuthenticationError,
    APIClientError,
    APIConnectionError,
    APIRateLimitError,
    APIResponseError,
    APITimeoutError,
    UnsupportedEndpointError,
)


@pytest.mark.parametrize(
    "exc_type",
    [
        APIConnectionError,
        APITimeoutError,
        APIAuthenticationError,
        APIRateLimitError,
        APIResponseError,
        UnsupportedEndpointError,
    ],
)
def test_all_exceptions_derive_from_base(exc_type: type[Exception]) -> None:
    assert issubclass(exc_type, APIClientError)


def test_response_error_carries_status_and_payload() -> None:
    error = APIResponseError("boom", status_code=500, payload={"detail": "oops"})
    assert error.status_code == 500
    assert error.payload == {"detail": "oops"}
    assert str(error) == "boom"
