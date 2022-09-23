from copy import deepcopy

from pydantic import BaseModel

from kayaku.backend import dumps, loads
from kayaku.pretty import Prettifier
from kayaku.utils import gen_schema, update


class A(BaseModel):
    val: int = 5


class B(BaseModel):
    a: A
    var: str


class C(BaseModel):
    foo: int


def test_schema_gen():
    assert gen_schema(
        [
            (("main", "a"), A),
            (("main", "b"), B),
            (("main", "c"), C),
        ]
    ) == {
        "$schema": "http://json-schema.org/schema",
        "type": "object",
        "properties": {
            "main": {
                "type": "object",
                "properties": {
                    "a": {"type": "object", "$ref": "#/$defs/A"},
                    "b": {"type": "object", "$ref": "#/$defs/B"},
                    "c": {"type": "object", "$ref": "#/$defs/C"},
                },
            }
        },
        "$defs": {
            "A": {
                "title": "A",
                "type": "object",
                "properties": {
                    "val": {"title": "Val", "default": 5, "type": "integer"}
                },
            },
            "B": {
                "title": "B",
                "type": "object",
                "properties": {
                    "a": {"$ref": "#/$defs/A"},
                    "var": {"title": "Var", "type": "string"},
                },
                "required": ["a", "var"],
            },
            "C": {
                "title": "C",
                "type": "object",
                "properties": {"foo": {"title": "Foo", "type": "integer"}},
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
