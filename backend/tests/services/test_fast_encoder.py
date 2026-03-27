from datetime import datetime, timezone
from dataclasses import dataclass
from app.services.cache import _fast_encoder

@dataclass
class CustomDictModel:
    a: int
    b: str

    def to_dict(self):
        return {"a": self.a, "b": self.b, "custom": True}

@dataclass
class StandardModel:
    c: float

def test_fast_encoder_with_to_dict():
    model = CustomDictModel(1, "test")
    result = _fast_encoder(model)
    assert result == {"a": 1, "b": "test", "custom": True}

def test_fast_encoder_without_to_dict():
    model = StandardModel(3.14)
    result = _fast_encoder(model)
    assert result == {"c": 3.14}

def test_fast_encoder_with_datetime():
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    result = _fast_encoder(dt)
    assert result == "2023-01-01T12:00:00+00:00"
