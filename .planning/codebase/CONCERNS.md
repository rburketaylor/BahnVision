# Codebase Concerns

**Analysis Date:** 2024-01-27

## Tech Debt

**Missing Explicit Database Configuration:**

- Issue: Database connection lacks isolation level and transaction configuration
- Files: `[backend/app/core/database.py]`
- Impact: Potential for race conditions and inconsistent reads under high load
- Fix approach: Add explicit isolation level configuration to SQLAlchemy engine settings

**Station Stats Line Aggregation:**

- Issue: Missing aggregation of `by_route_type` from daily summaries in `heatmap_service.py`
- Files: `[backend/app/services/heatmap_service.py:1293]`
- Impact: Most affected line calculation uses simplified logic, may not reflect accurate route performance
- Fix approach: Implement proper aggregation from daily summaries when available

**Async Test Functions Missing Markers:**

- Issue: Many async test functions lack explicit pytest-asyncio markers
- Files: Multiple test files in `[backend/tests/]`
- Impact: Test execution may fail or behave unexpectedly
- Fix approach: Add `@pytest.mark.asyncio` to all async test functions and use `async with AsyncClient` for test client usage

## Known Bugs

**Empty Return Patterns:**

- Issue: Multiple services return empty objects (`[]`, `{}`) on null/missing data
- Files: `[backend/app/services/transit_data.py]`, `[backend/app/services/gtfs_realtime.py]`
- Symptoms: Frontend may show "no data" instead of handling missing data gracefully
- Trigger: API endpoints called with missing parameters or external service failures
- Workaround: Add null checks and provide meaningful default responses in Pydantic models

## Security Considerations

**Debug Logs in Production:**

- Risk: Debug logs enabled via environment variable could expose sensitive information
- Files: `[frontend/src/lib/config.ts:18]`
- Current mitigation: Environment variable controlled, defaults to false
- Recommendations: Add runtime validation to ensure debug logs are disabled in production environments

**CORS Configuration:**

- Risk: Overly permissive CORS settings in development
- Files: `[.env.example:30]`
- Current mitigation: Localhost origins only for development
- Recommendations: Implement environment-specific CORS policies and validate origins in production

## Performance Bottlenecks

**Large Service Files:**

- Problem: Some service files are overly large (1400+ lines)
- Files: `[backend/app/services/heatmap_service.py]`
- Cause: Multiple responsibilities mixed in single file
- Improvement path: Split into focused modules (heatmap operations, aggregation, calculations)

**Network Averages Query Optimization:**

- Problem: Complex aggregation queries for network averages without proper indexing
- Files: `[backend/app/services/station_stats_service.py:499-578]`
- Cause: Summing across millions of records for time ranges longer than 48 hours
- Improvement path: Ensure proper indexing on `bucket_start`, `bucket_width_minutes`, and composite indexes for time-based queries

## Fragile Areas

**Async Session Management:**

- Why fragile: Database sessions created without explicit transaction boundaries
- Files: `[backend/app/core/database.py:40-43]`
- Safe modification: Always use explicit transactions with `async with session.begin():`
- Test coverage: Current tests use session markers but need transaction boundary validation

**Cache Exception Handling:**

- Why fragile: Cache operations catch generic Exception types
- Files: `[backend/app/services/cache.py]`, `[backend/app/services/station_stats_service.py:78-91]`
- Safe modification: Catch specific exception types (RedisConnectionError, TimeoutError)
- Test coverage: Need specific cache failure scenarios in integration tests

## Scaling Limits

**Database Pool Configuration:**

- Current capacity: Pool size 10, max overflow 10
- Limit: May become bottleneck under high concurrent requests
- Scaling path: Configure based on connection monitoring and implement connection pooling metrics

**Cache TTL Strategy:**

- Current capacity: Mix of TTLs from 30s to 24h
- Limit: Stale TTL fallback may serve outdated data too long
- Scaling path: Implement dynamic TTL adjustment based on data volatility and access patterns

## Dependencies at Risk

**Valkey Dependency:**

- Risk: Single cache point of failure
- Impact: Entire application caching fails if Valkey unavailable
- Migration plan: Implement multi-layer cache with persistent fallback option

**Pydantic v2:**

- Risk: Heavy dependency on Pydantic for validation and serialization
- Impact: Model changes require extensive updates
- Migration plan: Plan for gradual migration to alternative validation if performance becomes issue

## Missing Critical Features

**Transaction Isolation Levels:**

- Problem: No explicit transaction isolation configuration
- Blocks: Cannot guarantee data consistency during concurrent operations
- Priority: High for financial/critical transit data operations

**Database Migration Monitoring:**

- Problem: No visibility into migration success/failure
- Blocks: Cannot detect partial or failed migrations
- Priority: Medium for production reliability

## Test Coverage Gaps

**Cache Failure Scenarios:**

- What's not tested: Behavior when Valkey becomes unavailable during operations
- Files: `[backend/tests/services/test_cache_compatibility.py]`
- Risk: Circuit breaker logic untested, may not handle failures gracefully
- Priority: High - cache failures are common in distributed systems

**Database Transaction Boundaries:**

- What's not tested: Rollback behavior and data consistency after failures
- Files: All repository and service tests
- Risk: Data corruption if partial writes occur
- Priority: High for data integrity

---

_Concerns audit: 2024-01-27_
