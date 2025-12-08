# GTFS Testing Plan

This document outlines the testing strategy for the GTFS migration, including new tests to add and MVG tests to deprecate.

## Overview

As we migrate from MVG API to GTFS/GTFS-RT data sources, we need to:
1. Add comprehensive tests for new GTFS components
2. Maintain MVG tests during the transition period (Phases 1-3)
3. Remove MVG tests after full migration (Phase 4)

## Phase 1: GTFS Foundation Tests

### Unit Tests for Models (`backend/tests/models/test_gtfs.py`)

```python
# Test all GTFS SQLAlchemy models
- test_gtfs_stop_model_creation
- test_gtfs_route_model_creation  
- test_gtfs_trip_model_creation
- test_gtfs_stop_time_model_with_interval  # Important: >24h time support
- test_gtfs_calendar_model_creation
- test_gtfs_calendar_date_model_creation
- test_gtfs_feed_info_model_creation
- test_gtfs_trip_stop_times_relationship
- test_gtfs_route_trips_relationship
```

### Unit Tests for GTFSFeedImporter (`backend/tests/services/test_gtfs_feed.py`)

```python
# Test feed download and parsing
- test_download_feed_success
- test_download_feed_http_error
- test_download_feed_invalid_zip
- test_parse_feed_with_gtfs_kit

# Test persistence methods
- test_persist_stops_upsert
- test_persist_routes_upsert
- test_persist_trips_upsert
- test_persist_stop_times_batch_insert
- test_persist_calendar_upsert
- test_persist_calendar_dates_upsert
- test_persist_calendar_dates_with_exceptions
- test_persist_calendar_dates_empty_df
- test_persist_feed_info_upsert

# Test time conversion edge cases
- test_convert_time_to_interval_standard_time
- test_convert_time_to_interval_over_24h  # e.g., "26:30:00"
- test_convert_time_to_interval_invalid_format
- test_convert_time_to_interval_none_input

# Test full import workflow
- test_import_feed_success
- test_import_feed_partial_data  # Some tables empty
- test_import_feed_rollback_on_error
```

### Unit Tests for GTFSScheduleService (`backend/tests/services/test_gtfs_schedule.py`)

```python
# Test departure queries
- test_get_stop_departures_by_id
- test_get_stop_departures_by_name
- test_get_stop_departures_with_time_filter
- test_get_stop_departures_limit_offset
- test_get_stop_departures_not_found_raises

# Test stop search
- test_search_stops_by_name
- test_search_stops_fuzzy_match
- test_search_stops_limit
- test_search_stops_no_results

# Test get all stops (for heatmap)
- test_get_all_stops_returns_all
- test_get_all_stops_respects_limit
- test_get_all_stops_empty_database

# Test nearby stops (PostGIS)
- test_get_nearby_stops_returns_sorted_by_distance
- test_get_nearby_stops_radius_filter
- test_get_nearby_stops_empty_area
```

### Unit Tests for GTFSFeedScheduler (`backend/tests/jobs/test_gtfs_scheduler.py`)

```python
# Test scheduler lifecycle
- test_scheduler_start_schedules_job
- test_scheduler_stop_shuts_down
- test_scheduler_initial_import_on_empty_db

# Test update logic
- test_check_and_update_triggers_on_stale_feed
- test_check_and_update_skips_fresh_feed
- test_update_feed_error_handling
```

### Integration Tests (`backend/tests/api/v1/test_gtfs_endpoints.py`)

```python
# Note: These require database fixtures with GTFS data

# Test departures endpoint (future Phase 2)
- test_gtfs_departures_endpoint_returns_scheduled_data
- test_gtfs_departures_filters_by_transport_type
- test_gtfs_departures_pagination

# Test station search endpoint
- test_gtfs_station_search_returns_results
- test_gtfs_station_search_empty_query
```

### Integration Tests for Transit API (`backend/tests/api/v1/test_transit.py`)

```python
# Test departures endpoint
- test_transit_departures_endpoint_success
- test_transit_departures_endpoint_stop_not_found
- test_transit_departures_endpoint_with_limit
- test_transit_departures_endpoint_with_offset_minutes
- test_transit_departures_response_structure

# Test stops search endpoint
- test_transit_stops_search_endpoint_success
- test_transit_stops_search_endpoint_empty_results
- test_transit_stops_search_endpoint_with_limit

# Test stop details endpoint
- test_transit_stop_details_endpoint_success
- test_transit_stop_details_endpoint_not_found

# Test nearby stops endpoint
- test_transit_stops_nearby_endpoint_success
- test_transit_stops_nearby_endpoint_with_radius
```

## Phase 2: GTFS-RT Tests

### Unit Tests for GTFSRealtimeService (`backend/tests/services/test_gtfs_realtime.py`)

```python
# Test protobuf parsing
- test_parse_trip_updates_feed
- test_parse_vehicle_positions_feed
- test_parse_service_alerts_feed
- test_handle_malformed_protobuf

# Test delay calculation
- test_calculate_delay_from_trip_update
- test_handle_missing_stop_time_update
- test_handle_cancelled_trip

# Test caching
- test_realtime_data_cached_with_short_ttl
- test_realtime_cache_invalidation

# Test circuit breaker behavior
- test_circuit_breaker_opens_after_threshold_failures
- test_circuit_breaker_transitions_to_half_open_after_recovery
- test_circuit_breaker_closes_on_success
- test_circuit_breaker_blocks_requests_when_open

# Test vehicle positions
- test_fetch_vehicle_positions_success
- test_fetch_vehicle_positions_missing_position_data
- test_fetch_vehicle_positions_missing_trip_data
- test_store_vehicle_positions_in_cache

# Test service alerts
- test_fetch_alerts_success
- test_fetch_alerts_extracts_affected_routes
- test_fetch_alerts_extracts_affected_stops
- test_fetch_alerts_handles_active_period
- test_store_alerts_in_cache
- test_map_cause_values
- test_map_effect_values
```

### Unit Tests for TransitDataService (`backend/tests/services/test_transit_data.py`)

```python
# Test departure retrieval
- test_get_departures_for_stop_basic
- test_get_departures_for_stop_with_offset
- test_get_departures_for_stop_applies_realtime_updates
- test_get_departures_for_stop_without_realtime
- test_get_departures_for_stop_empty_results

# Test route info
- test_get_route_info_basic
- test_get_route_info_with_alerts
- test_get_route_info_caching
- test_get_route_info_not_found

# Test stop info
- test_get_stop_info_basic
- test_get_stop_info_with_departures
- test_get_stop_info_caching
- test_get_stop_info_not_found

# Test search
- test_search_stops_returns_stop_info
- test_search_stops_empty_query

# Test vehicle tracking
- test_get_vehicle_position_delegates_to_realtime

# Test real-time refresh
- test_refresh_real_time_data_parallel_fetch
- test_refresh_real_time_data_handles_exceptions
```

### Unit Tests for Dataclass Models (`backend/tests/services/test_gtfs_dataclasses.py`)

```python
# Test dataclass __post_init__ defaults
- test_trip_update_defaults_timestamp
- test_vehicle_position_defaults_timestamp
- test_service_alert_defaults_timestamp
- test_departure_info_defaults_alerts_list
- test_route_info_defaults_alerts_list
- test_stop_info_defaults_lists
```

## Phase 3: Hybrid Mode Tests

### Integration Tests (`backend/tests/api/v1/test_hybrid_departures.py`)

```python
# Test fallback behavior
- test_departures_uses_gtfs_when_available
- test_departures_falls_back_to_mvg_on_gtfs_error
- test_departures_merges_realtime_with_schedule

# Test consistency
- test_response_format_matches_between_sources
- test_station_id_mapping_mvg_to_gtfs
```

## Phase 4: MVG Deprecation

### Tests to Remove

After full GTFS migration is complete and validated, remove:

```
backend/tests/api/v1/test_mvg.py           # All MVG endpoint tests (~800 lines)
backend/tests/services/test_mvg_client.py  # MVG client tests
backend/tests/conftest.py                  # FakeMVGClient fixtures
backend/tests/api/conftest.py              # MVGClientScenario, FakeMVGClient
```

### Migration Checklist

- [ ] All GTFS tests passing
- [ ] GTFS coverage >= MVG coverage
- [ ] No production traffic to MVG endpoints for 2 weeks
- [ ] Feature flags fully switched to GTFS
- [ ] Remove MVG client code
- [ ] Remove MVG tests
- [ ] Update documentation

## Test Fixtures Required

### Database Fixtures (`backend/tests/fixtures/gtfs_data.py`)

```python
# Provide reusable GTFS test data
- create_test_gtfs_stops() -> list[GTFSStop]
- create_test_gtfs_routes() -> list[GTFSRoute]
- create_test_gtfs_trips() -> list[GTFSTrip]
- create_test_gtfs_stop_times() -> list[GTFSStopTime]
- create_test_gtfs_calendar() -> list[GTFSCalendar]
- seed_gtfs_test_database(session) -> None
```

### Mock Services (`backend/tests/mocks/`)

```python
# FakeGTFSFeedImporter - returns canned data without HTTP
# FakeGTFSRealtimeClient - returns canned protobuf responses
```

## Testing Infrastructure Updates

### conftest.py Additions

```python
@pytest.fixture
def gtfs_test_data(db_session):
    """Seed database with GTFS test data."""
    from tests.fixtures.gtfs_data import seed_gtfs_test_database
    seed_gtfs_test_database(db_session)
    yield
    # Cleanup handled by db_session fixture

@pytest.fixture
def fake_gtfs_feed_importer():
    """Fake importer that doesn't make HTTP calls."""
    return FakeGTFSFeedImporter()

@pytest.fixture  
def fake_gtfs_realtime_client():
    """Fake realtime client with canned responses."""
    return FakeGTFSRealtimeClient()
```

## Coverage Goals

| Component | Target Coverage |
|-----------|-----------------|
| `models/gtfs.py` | 100% |
| `services/gtfs_feed.py` | 90% |
| `services/gtfs_schedule.py` | 95% |
| `services/gtfs_realtime.py` | 90% |
| `services/transit_data.py` | 90% |
| `jobs/gtfs_scheduler.py` | 85% |
| API endpoints | 90% |

## Implementation Priority

1. **Immediate (Phase 1)**
   - [ ] `test_gtfs.py` - Model tests
   - [ ] `test_gtfs_feed.py` - Importer tests
   - [ ] `test_gtfs_schedule.py` - Schedule service tests
   - [ ] `test_gtfs_scheduler.py` - Scheduler tests
   - [ ] GTFS fixtures

2. **Phase 2**
   - [ ] `test_gtfs_realtime.py` - Realtime service tests (including circuit breaker)
   - [ ] `test_transit_data.py` - Combined transit data service tests
   - [ ] `test_gtfs_dataclasses.py` - Dataclass model tests
   - [ ] Realtime mock client

3. **Phase 3**
   - [ ] `test_transit.py` - Transit API endpoint tests
   - [ ] `test_hybrid_departures.py` - Fallback tests
   - [ ] Integration tests with both sources

4. **Phase 4**
   - [ ] Verify GTFS test coverage
   - [ ] Remove MVG tests
   - [ ] Clean up MVG fixtures
