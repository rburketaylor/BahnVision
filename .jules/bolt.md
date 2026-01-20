# Bolt Journal

## 2026-01-09 - GTFS-RT Fetch Optimization
**Learning:** Consolidating multiple API requests to the same endpoint into a single request significantly reduces overhead, especially when parsing large payloads like protobuf feeds.
**Action:** When working with combined feeds (like GTFS-RT), check if the same URL is being fetched multiple times concurrently for different entity types. If so, refactor to fetch once and process in memory. Also, ensure return types are consistent (dictionaries vs lists) to prevent runtime errors in consumers.

## 2026-01-20 - [Optimizing GTFS Schedule Lookups]
**Learning:** Redundant "exists?" checks before queries are common N+1 patterns. API layers often validate existence (returning 404), so data services can skip this check if the "not found" query result (empty list) is handled gracefully.
**Action:** When seeing `if not exists: raise Error` followed by a query, check if the caller actually needs that specific error or if an empty result is sufficient. If so, make the check optional.
