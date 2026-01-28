# Testing Patterns

**Analysis Date:** 2024-01-27

## Test Framework

**Backend:**

- **Runner:** pytest with async mode
- **Client:** FastAPI TestClient
- **Markers:** `@pytest.mark.integration`, `@pytest.mark.slow`
- **Coverage:** 70% minimum, branch coverage enabled
- **Config:** `backend/pyproject.toml`

**Frontend:**

- **Runner:** Vitest with jsdom environment
- **Client:** React Testing Library with userEvent
- **Mocking:** MSW (Mock Service Worker) for API mocking
- **Coverage:** 60% minimum for lines/functions/branches
- **Config:** `frontend/vitest.config.ts`

## Test Structure

**Backend Organization:**

```
backend/tests/
├── api/               # HTTP endpoint tests
├── services/          # Business logic tests
├── core/             # Infrastructure tests
├── persistence/      # Database/repository tests
└── conftest.py       # Shared fixtures
```

**Frontend Organization:**

```
frontend/src/tests/
├── unit/             # Component and utility tests
├── __mocks__/        # Custom mocks
├── setup.ts          # Test setup
└── mocks/            # MSW handlers
```

**Test File Naming:**

- Python: `test_*.py` (e.g., `test_cache_primitives.py`)
- TypeScript: `*.test.ts[x]` (e.g., `DeparturesBoard.test.tsx`)

## Test Patterns

**Backend Test Structure:**

```python
# backend/tests/services/test_cache_primitives.py
import pytest
from unittest.mock import Mock, patch
from app.services.cache import CircuitBreaker, TTLConfig

class TestTTLConfig:
    """Tests for TTLConfig."""

    @pytest.fixture
    def mock_settings(self):
        with patch("app.services.cache.get_settings") as mock:
            settings = Mock(spec=Settings)
            settings.valkey_cache_ttl_seconds = 300
            mock.return_value = settings
            yield settings

    def test_init_reads_settings(self, mock_settings):
        config = TTLConfig()
        assert config.valkey_cache_ttl == 300

    def test_get_effective_ttl_returns_override(self, mock_settings):
        config = TTLConfig()
        assert config.get_effective_ttl(10) == 10
```

**Frontend Test Structure:**

```typescript
// frontend/src/tests/unit/DeparturesBoard.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import { DeparturesBoard } from '../../components/DeparturesBoard'
import type { TransitDeparture } from '../../types/gtfs'

describe('DeparturesBoard', () => {
  it('orders departures by effective realtime/scheduled timestamps', () => {
    const departures: TransitDeparture[] = [
      buildDeparture({
        headsign: 'Later Train',
        route_short_name: 'U6',
        scheduled_departure: '2024-01-01T10:00:00Z',
        realtime_departure: '2024-01-01T10:10:00Z',
      }),
      // More test data...
    ]

    render(<DeparturesBoard departures={departures} />)

    const destinationsInOrder = screen
      .getAllByText(/Later Train|Early Planned|Earlier Real/)
      .map(element => element.textContent)

    expect(destinationsInOrder).toEqual(['Early Planned', 'Earlier Real', 'Later Train'])
  })

  it('toggles between 24h and 12h display', async () => {
    const user = userEvent.setup()
    // Test implementation...
  })
})
```

## Mocking

**Backend Mocks:**

```python
# backend/tests/conftest.py
class FakeValkey:
    """In-memory Valkey replacement used for tests."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}
        self.should_fail = False

    async def get(self, key: str) -> str | None:
        if self.should_fail:
            raise RuntimeError("valkey unavailable")
        record = self._store.get(key)
        return record[0] if record else None

@pytest.fixture()
def fake_valkey() -> FakeValkey:
    return FakeValkey()

@pytest.fixture()
def cache_service(fake_valkey: FakeValkey) -> CacheService:
    return CacheService(fake_valkey)
```

**Frontend Mocks:**

```typescript
// frontend/src/tests/mocks/server.ts
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);

// frontend/src/tests/mocks/handlers.ts
import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/v1/departures", () => {
    return HttpResponse.json([
      {
        trip_id: "trip_1",
        route_short_name: "U1",
        headsign: "Destination",
        // Mock data...
      },
    ]);
  }),
];
```

## Fixtures and Factories

**Backend Fixtures:**

```python
# Backend test factories
def build_departure(overrides: dict) -> dict:
    base_departure = {
        'trip_id': 'trip_1',
        'route_id': 'U1',
        'route_short_name': 'U1',
        # Base data...
    }
    return { **base_departure, **overrides }
```

**Frontend Test Data:**

```typescript
// Frontend test data factory
const baseDeparture: TransitDeparture = {
  trip_id: "trip_1",
  route_id: "U1",
  route_short_name: "U1",
  route_long_name: "U-Bahn Line 1",
  headsign: "Default Destination",
  // Base data...
};

const buildDeparture = (
  overrides: Partial<TransitDeparture>,
): TransitDeparture => ({
  ...baseDeparture,
  ...overrides,
});
```

## Coverage

**Backend Coverage:**

- Target: 70% minimum
- Exclude test files, **pycache**, conftest.py
- Show missing lines in reports
- HTML output: `htmlcov/`
- XML output: `coverage.xml`

**Frontend Coverage:**

- Target: 60% minimum for all metrics
- Exclude tests, node_modules, dist
- Reports: text, json, html, lcov

```typescript
// frontend/vitest.config.ts
coverage: {
  provider: 'v8',
  reporter: ['text', 'json', 'html', 'lcov'],
  thresholds: {
    lines: 60,
    functions: 60,
    branches: 55,
    statements: 60,
  },
}
```

## Test Types

**Unit Tests:**

- Isolated component/function testing
- Mock external dependencies
- Fast execution (seconds)
- Example: `test_cache_primitives.py`, `DeparturesBoard.test.tsx`

**Integration Tests:**

- Multi-component interaction
- Real external services (with test doubles)
- Medium execution time (tens of seconds)
- Example: API endpoint tests, database operations

**E2E Tests:**

- Full user journey testing
- Real browser (Playwright)
- Slow execution (minutes)
- Example: `npm run test:e2e`

## Common Patterns

**Async Testing:**

```python
# Python async tests
@pytest.mark.asyncio
async def test_cache_set_get():
    await cache_service.set_json("key", {"data": "value"})
    result = await cache_service.get_json("key")
    assert result == {"data": "value"}
```

```typescript
// TypeScript async testing
import { waitFor } from '@testing-library/react'

it('loads departures on mount', async () => {
  render(<DeparturesBoard departures={[]} />)
  await waitFor(() => {
    expect(screen.getByText('Loading')).toBeInTheDocument()
  })
})
```

**Error Testing:**

```python
# Python error testing
def test_circuit_breaker_opens_on_failure():
    with patch('app.services.cache.get_valkey_client') as mock_client:
        mock_client.return_value.get.side_effect = Exception("Connection failed")

        # First call opens circuit
        result = await cache_service.get("key")
        assert result is None

        # Subsequent calls fail fast
        result = await cache_service.get("key")
        assert result is None
```

```typescript
// TypeScript error testing
it('shows error message when API fails', async () => {
  server.use(
    http.get('/api/v1/departures', () => HttpResponse.error())
  )

  render(<DeparturesBoard departures={[]} />)
  expect(screen.getByText('Failed to load departures')).toBeInTheDocument()
})
```

## Test Utilities

**Backend Helpers:**

```python
# backend/tests/service_availability.py
def skip_if_no_valkey():
    """Skip test if Valkey is not available."""
    if not is_valkey_available():
        pytest.skip("Valkey not available")

@requires_valkey
def test_cache_with_real_valkey():
    # Test using actual Valkey
    pass
```

**Frontend Setup:**

```typescript
// frontend/src/tests/setup.ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});

// Mock environment variables
process.env.VITE_API_BASE_URL = "http://localhost:8000";
```

---

_Testing analysis: 2024-01-27_
