"""MVG-specific exception definitions."""

from __future__ import annotations


class StationNotFoundError(Exception):
    """Raised when an MVG station cannot be resolved."""


class MVGServiceError(Exception):
    """Generic wrapper for MVG service failures."""


class RouteNotFoundError(Exception):
    """Raised when MVG cannot provide a route between two stations."""


__all__ = [
    "StationNotFoundError",
    "MVGServiceError",
    "RouteNotFoundError",
]
