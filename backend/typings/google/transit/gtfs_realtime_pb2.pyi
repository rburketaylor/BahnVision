from typing import Any, List

class FeedHeader:
    timestamp: int

class FeedMessage:
    header: FeedHeader
    entity: List[Any]

    def ParseFromString(self, data: bytes) -> None: ...
