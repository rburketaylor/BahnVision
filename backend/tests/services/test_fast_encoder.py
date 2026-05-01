from app.services.cache import _fast_encoder


class DummyWithToDict:
    def to_dict(self):
        return {"a": 1}


class DummyWithoutToDict:
    def __init__(self):
        self.b = 2


def test_fast_encoder_with_to_dict():
    obj = DummyWithToDict()
    result = _fast_encoder(obj)
    assert result == {"a": 1}


def test_fast_encoder_without_to_dict():
    obj = DummyWithoutToDict()
    result = _fast_encoder(obj)
    assert result == {"b": 2}


def test_fast_encoder_none():
    assert _fast_encoder(None) is None


def test_fast_encoder_list():
    assert _fast_encoder(["a"]) == ["a"]


def test_fast_encoder_dict():
    assert _fast_encoder({"a": 1}) == {"a": 1}
