## 2025-05-23 - Batching Queries in SQLAlchemy AsyncSession
**Learning:** `AsyncSession` does not support concurrent execution of queries (e.g. via `asyncio.gather`), which often forces sequential execution. However, independent queries can often be combined using `UNION ALL` to reduce DB round-trips.
**Action:** When fetching data from multiple tables that share a common structure (like IDs or codes), use `union_all` and process the result stream in Python instead of awaiting multiple sequential queries.
