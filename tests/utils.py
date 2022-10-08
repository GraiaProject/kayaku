import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum

from kayaku.backend import dumps, loads
from kayaku.backend.types import JObject
from kayaku.pretty import Prettifier
from kayaku.schema_gen import gen_schema_from_list
from kayaku.utils import KayakuEncoder, from_dict, update

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
        {},
        "deleted"
    ],
    "p": [],
    "v": {"a": 5}
}
"""

update_output_del = """\
{
    "a": "b", // sigma
    // preserved
    "d": "e",
    // updated
    "h": 4,
    "j": [
        /*nice*/
        "viva",
        {}
    ],
    "p": [
        1,
        2
    ],
    "v": {"a": 5}
}"""

update_output_no_del = """\
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
        {}
    ],
    "p": [
        1,
        2
    ],
    "v": {"a": 5}
}"""


def test_json_update():
    o_obj = loads(update_input)
    obj = deepcopy(o_obj)
    del obj["f"]
    obj["h"] = 4
    obj["j"].pop()
    obj["p"].extend([1, 2])
    update(o_obj, obj, delete=True)
    assert dumps(Prettifier().prettify(o_obj)) == update_output_del
    o_obj = loads(update_input)
    update(o_obj, obj)
    assert dumps(Prettifier().prettify(o_obj)) == update_output_no_del


class E(Enum):
    A = 1
    B = 2
    C = 3


def test_extra_load():
    ...


def test_extra_dump():
    from kayaku.backend import dumps
    from kayaku.pretty import Prettifier

    dt_now = datetime.now()

    assert (
        dumps(
            Prettifier().prettify(
                JObject(
                    {
                        "a": E.A,
                        "b": dt_now.date(),
                        "c": dt_now.time(),
                        "d": dt_now,
                        "e": re.compile(r"(?P<name>\d+)"),
                    }
                )
            ),
            KayakuEncoder,
        )
        == rf"""{{
    "a": 1,
    "b": "{dt_now.date().isoformat()}",
    "c": "{dt_now.time().isoformat()}",
    "d": "{dt_now.isoformat()}",
    "e": "(?P<name>\\d+)"
}}"""
    )


def test_extra_load():
    dt_now = datetime.now()

    @dataclass
    class Obj:
        a: E
        b: date
        c: time
        d: datetime
        e: re.Pattern

    obj = {
        "a": 1,
        "b": f"{dt_now.date().isoformat()}",
        "c": f"{dt_now.time().isoformat()}",
        "d": f"{dt_now.isoformat()}",
        "e": r"(?P<name>\d+)",
    }
    assert from_dict(Obj, obj) == Obj(
        E.A, dt_now.date(), dt_now.time(), dt_now, re.compile(r"(?P<name>\d+)")
    )
