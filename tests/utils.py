import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum

from helper import prettifier

from kayaku.backend import dumps, loads
from kayaku.backend.types import JObject, JWrapper
from kayaku.utils import copying_field, from_dict, update

update_input = """\
{
    "a": "b", // sigma
    // preserved
    "d": "e",
    //lost
    "f": "g",
    // updated
    "h": "i",
    "j": [
        /*nice*/
        "viva",
        {} /*test*/,
        "deleted"
    ],
    "p": [],
    "v": {"a": 5},
    "q": {/*comment*/"p": 1}
}
"""

update_output = """\
{
    "a": "b", // sigma
    // preserved
    "d": "e",
    //lost
    "f": "g",
    // updated
    "h": 4,
    "j": [
        /*nice*/
        "viva",
        /*test*/
        {}
    ],
    "p": [
        1,
        2,
        {"a": "b"}
    ],
    "v": {"a": 5},
    "q": {"a": 1},
    "k": "2022-01-01T08:00:00",
    "re": "(\\\\d+)"
}"""


def test_json_update():
    o_obj = loads(update_input)
    obj = deepcopy(o_obj)
    del obj["f"]
    obj["h"] = 4
    obj["j"].pop()
    obj["k"] = datetime(2022, 1, 1, 8, 0, 0)
    obj["re"] = re.compile(r"(\d+)")
    obj["p"].extend([1, 2, {"a": "b"}])
    obj["q"] = Sub(1)
    update(o_obj, obj)
    assert dumps(prettifier().prettify(o_obj)) == update_output


class E(Enum):
    A = 1
    B = 2
    C = 3


@dataclass
class Obj:
    a: E
    b: date
    c: time
    d: datetime
    e: re.Pattern
    f: list | bool
    g: int | None
    h: int | str


@dataclass
class Sub:
    a: int


@dataclass
class Obj2:
    a: E
    b: date
    c: time
    d: datetime
    e: re.Pattern
    f: list | bool
    g: int | None
    h: int | str
    i: dict[str, None | str]


def test_extra_load():
    dt_now = datetime.now()

    obj = {
        "a": 1,
        "b": f"{dt_now.date().isoformat()}",
        "c": f"{dt_now.time().isoformat()}",
        "d": f"{dt_now.isoformat()}",
        "e": r"(?P<name>\d+)",
        "f": JWrapper(True),
        "g": JWrapper(None),
        "h": "abc",
        "i": {"a": "a", "b": None},
    }
    target_obj = Obj2(
        E.A,
        dt_now.date(),
        dt_now.time(),
        dt_now,
        re.compile(r"(?P<name>\d+)"),
        True,
        None,
        "abc",
        {"a": "a", "b": None},
    )
    o: Obj2 = from_dict(Obj2, obj)
    assert o == target_obj
    assert o.f is True
    assert o.g is None
    assert o.i["b"] is None


def test_update_with_dc():
    from kayaku.backend.types import Array, Integer, JString, JWrapper

    dt_now = datetime.now()
    target_obj = Obj(
        E.A,
        dt_now.date(),
        dt_now.time(),
        dt_now,
        re.compile(r"(?P<name>\d+)"),
        [E.A, True, re.compile(r"(?P<name>.*?)"), dt_now, Sub(1), [5]],
        None,
        "abc",
    )
    o = JObject()
    update(o, target_obj)
    for k, v in JObject(
        {
            "a": Integer(1),
            "b": JString(dt_now.date().isoformat()),
            "c": JString(dt_now.time().isoformat()),
            "d": JString(dt_now.isoformat()),
            "e": JString("(?P<name>\\d+)"),
            "f": Array(
                [
                    Integer(1),
                    JWrapper(True),
                    JString(r"(?P<name>.*?)"),
                    JString(dt_now.isoformat()),
                    JObject({"a": Integer(1)}),
                    Array([Integer(5)]),
                ]
            ),
            "g": JWrapper(None),
            "h": JString("abc"),
        }
    ).items():
        assert o[k] == v
        assert o[k].__class__ == v.__class__


def test_copying_field():
    @dataclass
    class DC:
        ls: list = copying_field([])

    assert DC() == DC([])
