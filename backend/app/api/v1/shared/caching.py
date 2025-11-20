"""
Compatibility wrapper for shared caching utilities.

Prefer importing from cache_protocols.py, cache_flow.py, or cache_manager.py directly.
"""

from __future__ import annotations

from app.api.v1.shared.cache_flow import (
    execute_background_refresh,
    execute_cache_refresh,
    handle_cache_errors,
    handle_cache_lookup,
)
from app.api.v1.shared.cache_manager import CacheManager
from app.api.v1.shared.cache_protocols import (
    CacheRefreshProtocol,
    CacheResult,
    MvgCacheProtocol,
)

__all__ = [
    "CacheManager",
    "CacheRefreshProtocol",
    "CacheResult",
    "MvgCacheProtocol",
    "execute_background_refresh",
    "execute_cache_refresh",
    "handle_cache_errors",
    "handle_cache_lookup",
]
