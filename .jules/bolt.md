# Bolt Journal

## 2026-01-09 - GTFS-RT Fetch Optimization
**Learning:** Consolidating multiple API requests to the same endpoint into a single request significantly reduces overhead, especially when parsing large payloads like protobuf feeds.
**Action:** When working with combined feeds (like GTFS-RT), check if the same URL is being fetched multiple times concurrently for different entity types. If so, refactor to fetch once and process in memory. Also, ensure return types are consistent (dictionaries vs lists) to prevent runtime errors in consumers.
