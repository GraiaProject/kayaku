from copy import deepcopy
from dataclasses import dataclass

from kayaku.backend import dumps, loads
from kayaku.pretty import Prettifier
from kayaku.schema_gen import gen_schema_from_list
from kayaku.utils import update


@dataclass
class A:
    val: int = 5


@dataclass
class B:
    a: A
    var: str


@dataclass
class C:
    foo: int


A_name = f"{A.__module__}.{A.__qualname__}"
B_name = f"{B.__module__}.{B.__qualname__}"
C_name = f"{C.__module__}.{C.__qualname__}"


def test_schema_gen():
    assert gen_schema_from_list(
        [
            (("main", "a"), A),
            (("main", "b"), B),
            (("main", "c"), C),
        ]
    ) == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "main": {
                "type": "object",
                "properties": {
                    "a": {"allOf": [{"$ref": f"#/$defs/{A_name}"}]},
                    "b": {"allOf": [{"$ref": f"#/$defs/{B_name}"}]},
                    "c": {"allOf": [{"$ref": f"#/$defs/{C_name}"}]},
                },
                "required": ["a", "b", "c"],
            }
        },
        "required": ["main"],
        "$defs": {
            A_name: {
                "title": A_name,
                "type": "object",
                "properties": {"val": {"default": 5, "type": "integer"}},
            },
            B_name: {
                "title": B_name,
                "type": "object",
                "properties": {
                    "a": {"$ref": f"#/$defs/{A_name}"},
                    "var": {"type": "string"},
                },
                "required": ["a", "var"],
            },
            C_name: {
                "title": C_name,
                "type": "object",
                "properties": {"foo": {"type": "integer"}},
                "required": ["foo"],
            },
        },
    }


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
