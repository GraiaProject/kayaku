import inspect

from kayaku.backend.api import json5
from kayaku.backend.types import convert
from kayaku.pretty import Prettifier


def test_pretty_single_wrapped():
    origins = [convert(i) for i in [{"a": "b"}, {"a": 1}, [1], ["acc"], [], {}]]
    expected = ["""{"a": "b"}""", """{"a": 1}""", """[1]""", """["acc"]""", "[]", "{}"]

    for o, e in zip(origins, expected):
        assert json5.dumps(Prettifier().prettify(o)) == e


def test_pretty_single_unwrapped():
    origin = convert({"a": "b"})
    expected_unwrapped = inspect.cleandoc(
        """\
        {
            "a": "b"
        }
        """
    )
    assert (
        json5.dumps(Prettifier(unfold_single=True).prettify(origin))
        == expected_unwrapped
    )
    origin = convert({"a": 1})
    expected_unwrapped = inspect.cleandoc(
        """\
        {
            "a": 1
        }
        """
    )
    assert (
        json5.dumps(Prettifier(unfold_single=True).prettify(origin))
        == expected_unwrapped
    )
