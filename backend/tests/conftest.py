"""Shared pytest fixtures for backend tests.

Tests run against the real local Postgres database that the ETL pipeline
populates, rather than a mocked DB - consistent with how the rest of this
project is tested. Requires DATABASE_URL to be set (see .env.example).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
