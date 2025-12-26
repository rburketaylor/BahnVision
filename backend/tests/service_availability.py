"""
Service availability helpers for tests.

Provides utilities and pytest markers for gracefully handling
tests that require external services (Valkey, PostgreSQL).
"""

from __future__ import annotations

import socket
from functools import lru_cache

import pytest


def _check_service(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a TCP service is reachable."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


@lru_cache(maxsize=1)
def is_valkey_available() -> bool:
    """Check if Valkey/Redis is available at localhost:6379."""
    return _check_service("localhost", 6379)


@lru_cache(maxsize=1)
def is_postgres_available() -> bool:
    """Check if PostgreSQL is available at localhost:5432."""
    return _check_service("localhost", 5432)


def skip_if_no_valkey() -> None:
    """Skip the current test if Valkey is not available."""
    if not is_valkey_available():
        pytest.skip(
            "Valkey not available at localhost:6379. "
            "Start services with: docker compose up -d"
        )


def skip_if_no_postgres() -> None:
    """Skip the current test if PostgreSQL is not available."""
    if not is_postgres_available():
        pytest.skip(
            "PostgreSQL not available at localhost:5432. "
            "Start services with: docker compose up -d"
        )


def skip_if_no_services() -> None:
    """Skip the current test if either Valkey or PostgreSQL is unavailable."""
    if not is_valkey_available():
        pytest.skip(
            "Valkey not available at localhost:6379. "
            "Start services with: docker compose up -d"
        )
    if not is_postgres_available():
        pytest.skip(
            "PostgreSQL not available at localhost:5432. "
            "Start services with: docker compose up -d"
        )


# Pytest markers for service requirements
requires_valkey = pytest.mark.skipif(
    not is_valkey_available(),
    reason="Valkey not available at localhost:6379. Start with: docker compose up -d",
)

requires_postgres = pytest.mark.skipif(
    not is_postgres_available(),
    reason="PostgreSQL not available at localhost:5432. Start with: docker compose up -d",
)

requires_services = pytest.mark.skipif(
    not (is_valkey_available() and is_postgres_available()),
    reason="Services not available. Start with: docker compose up -d",
)
