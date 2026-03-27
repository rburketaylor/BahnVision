## 2024-03-25 - Fast JSON Serialization for DataClasses
**Learning:** Recursive Python traversal via FastAPI's `jsonable_encoder` is incredibly slow, adding significant overhead when repeatedly caching thousands of standard dataclass/Pydantic models (like `DepartureInfo`).
**Action:** When saving many objects to cache or JSON, leverage a `default` handler in `json.dumps` (e.g., `_fast_encoder`) to check for an explicit `.to_dict()` serialization method before falling back to `jsonable_encoder`. This speeds up serialization by 5-10x.
