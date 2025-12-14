from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.cache import get_cache_service  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.cache import CacheService  # noqa: E402

# Import service availability helpers for use in tests
from tests.service_availability import (  # noqa: E402, F401
    is_valkey_available,
    is_postgres_available,
    skip_if_no_valkey,
    skip_if_no_postgres,
    skip_if_no_services,
    requires_valkey,
    requires_postgres,
    requires_services,
)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "requires_valkey: skip test if Valkey is not available"
    )
    config.addinivalue_line(
        "markers", "requires_postgres: skip test if PostgreSQL is not available"
    )
    config.addinivalue_line(
        "markers", "requires_services: skip test if any service is unavailable"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")


class FakeValkey:
    """In-memory Valkey replacement used for tests."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}
        self.should_fail = False

    def _prune(self) -> None:
        now = time.monotonic()
        expired = [
            key
            for key, (_, expires_at) in self._store.items()
            if expires_at is not None and expires_at <= now
        ]
        for key in expired:
            self._store.pop(key, None)

    async def get(self, key: str) -> str | None:
        self._prune()
        if self.should_fail:
            raise RuntimeError("valkey unavailable")
        record = self._store.get(key)
        if record is None:
            return None
        value, _ = record
        return value

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool | None = None,
    ) -> bool:
        self._prune()
        if self.should_fail:
            raise RuntimeError("valkey unavailable")
        if nx:
            # Only set when key does not exist.
            if key in self._store:
                return False
        expires_at = time.monotonic() + ex if ex else None
        self._store[key] = (value, expires_at)
        return True

    async def delete(self, *keys: str) -> None:
        self._prune()
        if self.should_fail:
            raise RuntimeError("valkey unavailable")
        for key in keys:
            self._store.pop(key, None)


@pytest.fixture()
def fake_valkey() -> FakeValkey:
    return FakeValkey()


@pytest.fixture()
def cache_service(fake_valkey: FakeValkey) -> CacheService:
    return CacheService(fake_valkey)


@pytest.fixture()
def api_client(cache_service: CacheService) -> Iterator[TestClient]:
    """Create a test client with fake cache service.

    Note: Uses full app with rate limiter middleware that requires Valkey.
    """
    skip_if_no_valkey()

    app = create_app()
    app.dependency_overrides[get_cache_service] = lambda: cache_service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
