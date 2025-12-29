## 2024-05-23 - [Caching Scheduled Departures]
**Learning:** SQL queries for GTFS scheduled departures are complex and involve multiple joins. Caching these results significantly improves performance. However, because departures are queried relative to a specific time, caching needs to be done on a "whole day" basis and then filtered in memory to handle different request times effectively.
**Action:** When caching time-sensitive data, consider caching a larger dataset (e.g., full day) and filtering in memory, rather than caching small fragments that depend on the request timestamp.
