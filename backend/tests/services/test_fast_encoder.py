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
    # jsonable_encoder converts the object to a dict
    assert result == {"b": 2}
