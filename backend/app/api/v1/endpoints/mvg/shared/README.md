# MVG Shared Infrastructure

This directory contains shared utilities and infrastructure for the MVG API endpoints, extracted from the original `mvg.py` file to support modular endpoint organization.

## Files

### `__init__.py`
- Makes this directory a proper Python package
- Exports the main shared utilities for easy import
- Provides a clean public API for the shared infrastructure

### `utils.py`
Contains utility functions extracted from the original `mvg.py`:

- `ensure_aware_utc(value: datetime) -> datetime`
  - Converts naive datetimes to UTC-aware timestamps
  - Original location: lines 33-37 from `mvg.py`

- `get_client() -> MVGClient`
  - Creates a fresh MVG client instance per request
  - Original location: lines 40-42 from `mvg.py`

### `cache_keys.py`
Contains cache key generation functions extracted from the original `mvg.py`:

- `departures_cache_key(station, limit, offset, transport_types) -> str`
  - Generates cache keys for departures endpoint
  - Original location: lines 973-984 from `mvg.py`

- `station_search_cache_key(query, limit) -> str`
  - Generates cache keys for station search endpoint
  - Original location: lines 987-989 from `mvg.py`

- `route_cache_key(origin, destination, departure_time, arrival_time, transport_types) -> str`
  - Generates cache keys for route planning endpoint
  - Original location: lines 992-1011 from `mvg.py`

## Usage

```python
# Import shared utilities
from app.api.v1.endpoints.mvg.shared import (
    ensure_aware_utc,
    get_client,
    departures_cache_key,
    route_cache_key,
    station_search_cache_key,
)

# Use in endpoint implementations
client = get_client()
cache_key = departures_cache_key(station, limit, offset, transport_types)
utc_time = ensure_aware_utc(datetime.now())
```

## Benefits

- **Code Reuse**: Common utilities are available across all MVG endpoint modules
- **Consistency**: Standardized cache key generation ensures consistent caching behavior
- **Maintainability**: Changes to shared logic only need to be made in one place
- **Testability**: Shared utilities can be tested independently
- **Modularity**: Supports the planned splitting of MVG endpoints into separate files