# Coding Conventions

**Analysis Date:** 2024-01-27

## Naming Patterns

**Files:**

- Python: snake_case (e.g., `cache_service.py`, `gtfs_realtime.py`)
- TypeScript/TSX: PascalCase for components, camelCase for utilities (e.g., `DeparturesBoard.tsx`, `useDebouncedValue.ts`)
- Test files: `test_*.py` (Python), `*.test.ts[x]` (TypeScript)

**Functions:**

- Python: snake_case with descriptive names (e.g., `get_cache_service()`, `mset_json()`)
- TypeScript: camelCase for functions, PascalCase for components (e.g., `useDepartures()`, `DeparturesBoard`)
- Private methods: underscore prefix (e.g., `_get_from_valkey()`, `_set_to_valkey()`)

**Variables:**

- Python: snake_case (e.g., `valkey_cache_ttl`, `circuit_breaker_timeout`)
- TypeScript: camelCase (e.g., `use24Hour`, `departureDelaySeconds`)
- Constants: UPPER_SNAKE_CASE (e.g., `REQUEST_ID_HEADER`, `_STALE_SUFFIX`)

**Types:**

- TypeScript: PascalCase (e.g., `TransitDeparture`, `DeparturesBoardProps`)
- Python: PascalCase for classes (e.g., `TTLConfig`, `CacheService`)

## Code Style

**Formatting:**

- Python: Black formatter (4-space indent, line length 88)
- TypeScript: Prettier with 2-space indent
- Both: Trailing commas in multi-line structures

**Linting:**

- Python: Ruff for linting and formatting
- TypeScript: ESLint with React hooks and refresh plugins
- Pre-commit hooks enforce style automatically

**Python Style:**

```python
class CacheService:
    """Cache service with resilience patterns."""

    def __init__(self, client: valkey.Valkey) -> None:
        self._client = client
        self._config = TTLConfig()

    async def get_json(self, key: str) -> Any | None:
        """Retrieve a JSON document and decode it."""
        payload = await self._get_from_valkey(key)
        if payload is not None:
            record_cache_event("json", "hit")
            return json.loads(payload)
```

**TypeScript Style:**

```typescript
interface DeparturesBoardProps {
  departures: TransitDeparture[];
  use24Hour?: boolean;
}

export function DeparturesBoard({
  departures,
  use24Hour: initialUse24Hour = true,
}: DeparturesBoardProps) {
  const [use24Hour, setUse24Hour] = useState(initialUse24Hour);

  const sortedDepartures = useMemo(
    () =>
      [...departures].sort((a, b) => {
        const timeA = a.realtime_departure || a.scheduled_departure;
        const timeB = b.realtime_departure || b.scheduled_departure;
        return new Date(timeA).getTime() - new Date(timeB).getTime();
      }),
    [departures],
  );
}
```

## Import Organization

**Python:**

1. Standard library imports
2. Third-party imports
3. Local application imports

```python
import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import valkey.asyncio as valkey
from fastapi.encoders import jsonable_encoder

from app.core.config import get_settings
from app.core.metrics import record_cache_event
```

**TypeScript:**

1. React imports
2. Third-party library imports
3. Local imports

```typescript
import { useState, useMemo } from "react";
import type { TransitDeparture } from "../types/gtfs";
import { formatTime } from "../utils/time";
```

## Error Handling

**Python Patterns:**

```python
# Circuit breaker pattern
@self._circuit_breaker.protect
async def _get() -> str | None:
    try:
        return await self._client.get(key)
    except Exception as exc:
        logger.warning("Cache GET failed: %s", exc)
        raise

# Validation with Pydantic
@field_validator("valkey_cache_ttl")
@classmethod
    def validate_ttl(cls, v: int) -> int:
        if v < 0:
            raise ValueError("TTL cannot be negative")
        return v
```

**TypeScript Patterns:**

```typescript
// Error boundaries
class ErrorBoundary extends React.Component {
  state = { hasError: false }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return <ErrorCard message="Something went wrong" />
    }
    return this.props.children
  }
}
```

## Logging

**Python:**

```python
logger = logging.getLogger(__name__)

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

# Conditional logging
if self._circuit_breaker.is_open():
    logger.warning("Circuit breaker open, skipping Valkey operation")
```

**TypeScript:**

```typescript
// Console logging in development
if (process.env.VITE_ENABLE_DEBUG_LOGS === "true") {
  console.log("[Debug]", message, data);
}

// Error reporting
import { reportError } from "../services/errorTracking";
try {
  riskyOperation();
} catch (error) {
  reportError(error);
}
```

## Comments

**When to Comment:**

- Complex business logic (e.g., GTFS processing)
- Performance-critical sections
- Cache strategies and fallback patterns
- API response shape explanations

**Python Docstrings:**

```python
class CircuitBreaker:
    """
    Circuit breaker for cache operations.

    When Valkey becomes unavailable, the circuit opens and operations
    fail fast, falling back to the in-memory cache instead.
    """
```

**TypeScript/TSDoc:**

```typescript
/**
 * Retrieve multiple JSON documents and decode them.
 *
 * Uses the underlying mget for efficient batch retrieval from Valkey,
 * then deserializes each value. Falls back to in-memory cache for
 * keys not found in Valkey.
 */
async function mget_json(keys: string[]): Promise<Record<string, any>> {
  // Implementation
}
```

## Function Design

**Size:** Prefer functions under 50 lines
**Parameters:** 3-5 parameters maximum, use objects for complex parameters
**Return Values:** Use union types for nullable returns, avoid None/undefined when possible

**Async Patterns:**

```python
# Use async context managers
@asynccontextmanager
async def single_flight(self, key: str, ttl_seconds: int) -> AsyncIterator[None]:
    async with self._single_flight.acquire(key, ttl_seconds) as acquired:
        if not acquired:
            raise TimeoutError(f"Failed to acquire lock for {key}")
        yield
```

**React Hook Patterns:**

```typescript
// Custom hooks follow useX naming
const useDepartures = (stationId: string, options?: QueryOptions) => {
  return useQuery({
    queryKey: ["departures", stationId],
    queryFn: () => fetchDepartures(stationId),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};
```

## Module Design

**Exports:**

- Python: `__all__` list for explicit exports
- TypeScript: Named exports, avoid default exports

```python
__all__ = ["CacheService", "get_cache_service", "get_valkey_client"]
```

```typescript
export { useDepartures, useStationSearch } from "./hooks";
export { DeparturesBoard, StationSearch } from "./components";
```

**Barrel Files:**

```typescript
// src/index.ts - Main barrel
export * from "./components";
export * from "./hooks";
export * from "./services";
export * from "./types";
```

---

_Convention analysis: 2024-01-27_
