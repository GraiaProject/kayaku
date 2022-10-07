"""dataclass schema generator tests.

Modified from https://github.com/Peter554/dc_schema.


MIT License

Copyright (c) 2022 Peter Byfield

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import dataclasses
import datetime
import enum
import typing as t

from jsonschema.validators import Draft202012Validator

from kayaku.schema_gen import ConfigModel, SchemaAnnotation, SchemaGenerator


def get_schema(obj: type[ConfigModel]):
    class NameOnlyGen(SchemaGenerator):
        def retrieve_name(self, typ: t.Type) -> str:
            return typ.__name__

    return NameOnlyGen.from_dc(obj)


@dataclasses.dataclass
class DcPrimitives:
    b: bool
    i: int
    f: float
    s: str


def test_get_schema_primitives():
    schema = get_schema(DcPrimitives)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcPrimitives",
        "properties": {
            "b": {"type": "boolean"},
            "i": {"type": "integer"},
            "f": {"type": "number"},
            "s": {"type": "string"},
        },
        "required": ["b", "i", "f", "s"],
    }


@dataclasses.dataclass
class DcOptional:
    a: int = 42
    b: int = dataclasses.field(default=42)
    c: int = dataclasses.field(default_factory=lambda: 42)
    d: str = "foo"
    e: bool = False
    f: None = None
    g: float = 1.1
    h: tuple[int, float] = (1, 1.1)


def test_get_schema_optional_fields():
    """optional field === field with a default (!== t.Optional)"""
    schema = get_schema(DcOptional)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcOptional",
        "properties": {
            "a": {"type": "integer", "default": 42},
            "b": {"type": "integer", "default": 42},
            "c": {"type": "integer"},
            "d": {"type": "string", "default": "foo"},
            "e": {"type": "boolean", "default": False},
            "f": {"type": "null", "default": None},
            "g": {"type": "number", "default": 1.1},
            "h": {
                "type": "array",
                "prefixItems": [{"type": "integer"}, {"type": "number"}],
                "minItems": 2,
                "maxItems": 2,
                "default": [1, 1.1],
            },
        },
    }


@dataclasses.dataclass
class DcUnion:
    a: t.Union[int, str]


def test_get_schema_union():
    schema = get_schema(DcUnion)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcUnion",
        "properties": {"a": {"anyOf": [{"type": "integer"}, {"type": "string"}]}},
        "required": ["a"],
    }


@dataclasses.dataclass
class DcNone:
    a: None
    b: t.Optional[int]
    c: t.Union[None, int]


def test_get_schema_nullable():
    schema = get_schema(DcNone)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcNone",
        "properties": {
            "a": {"type": "null"},
            "b": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "c": {"anyOf": [{"type": "null"}, {"type": "integer"}]},
        },
        "required": ["a", "b", "c"],
    }


@dataclasses.dataclass
class DcDict:
    a: dict
    b: dict[str, int]


def test_get_schema_dict():
    schema = get_schema(DcDict)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcDict",
        "properties": {
            "a": {"type": "object"},
            "b": {"type": "object", "additionalProperties": {"type": "integer"}},
        },
        "required": ["a", "b"],
    }


@dataclasses.dataclass
class DcList:
    a: list
    b: list[bool]


def test_get_schema_list():
    schema = get_schema(DcList)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcList",
        "properties": {
            "a": {"type": "array"},
            "b": {"type": "array", "items": {"type": "boolean"}},
        },
        "required": ["a", "b"],
    }


@dataclasses.dataclass
class DcTuple:
    a: tuple
    b: tuple[int, ...]
    c: tuple[int, bool, str]


def test_get_schema_tuple():
    schema = get_schema(DcTuple)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcTuple",
        "properties": {
            "a": {"type": "array"},
            "b": {"type": "array", "items": {"type": "integer"}},
            "c": {
                "type": "array",
                "prefixItems": [
                    {"type": "integer"},
                    {"type": "boolean"},
                    {"type": "string"},
                ],
                "minItems": 3,
                "maxItems": 3,
            },
        },
        "required": ["a", "b", "c"],
    }


@dataclasses.dataclass
class DcRefsChild:
    c: str


@dataclasses.dataclass
class DcRefs:
    a: DcRefsChild
    b: list[DcRefsChild]


def test_get_schema_refs():
    schema = get_schema(DcRefs)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcRefs",
        "properties": {
            "a": {"$ref": "#/$defs/DcRefsChild"},
            "b": {
                "type": "array",
                "items": {"$ref": "#/$defs/DcRefsChild"},
            },
        },
        "required": ["a", "b"],
        "$defs": {
            "DcRefsChild": {
                "type": "object",
                "title": "DcRefsChild",
                "properties": {"c": {"type": "string"}},
                "required": ["c"],
            }
        },
    }


@dataclasses.dataclass
class DcRefsSelf:
    a: str
    b: t.Optional[DcRefsSelf]
    c: list[DcRefsSelf]


def test_get_schema_self_refs():
    schema = get_schema(DcRefsSelf)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcRefsSelf",
        "properties": {
            "a": {"type": "string"},
            "b": {"anyOf": [{"$ref": "#"}, {"type": "null"}]},
            "c": {"type": "array", "items": {"$ref": "#"}},
        },
        "required": ["a", "b", "c"],
    }


@dataclasses.dataclass
class DcLiteral:
    a: t.Literal[1, "two", 3, None]
    b: t.Literal[42, 43] = 42


def test_get_schema_literal():
    schema = get_schema(DcLiteral)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcLiteral",
        "properties": {
            "a": {"enum": [1, "two", 3, None]},
            "b": {"enum": [42, 43], "default": 42},
        },
        "required": ["a"],
    }


class MyEnum(enum.Enum):
    a = enum.auto()
    b = enum.auto()


@dataclasses.dataclass
class DcEnum:
    a: MyEnum
    b: MyEnum = MyEnum.a


def test_get_schema_enum():
    schema = get_schema(DcEnum)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcEnum",
        "properties": {
            "a": {"$ref": "#/$defs/MyEnum"},
            "b": {"$ref": "#/$defs/MyEnum", "default": 1},
        },
        "required": ["a"],
        "$defs": {"MyEnum": {"title": "MyEnum", "enum": [1, 2]}},
    }


@dataclasses.dataclass
class DcSet:
    a: set
    b: set[int]


def test_get_schema_set():
    schema = get_schema(DcSet)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcSet",
        "properties": {
            "a": {"type": "array", "uniqueItems": True},
            "b": {"type": "array", "items": {"type": "integer"}, "uniqueItems": True},
        },
        "required": ["a", "b"],
    }


@dataclasses.dataclass
class DcStrAnnotated:
    a: t.Annotated[str, SchemaAnnotation(min_length=3, max_length=5)]
    b: t.Annotated[
        str, SchemaAnnotation(format="date", pattern=r"^\d.*")
    ] = "2000-01-01"


def test_get_schema_str_annotation():
    schema = get_schema(DcStrAnnotated)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcStrAnnotated",
        "properties": {
            "a": {"type": "string", "minLength": 3, "maxLength": 5},
            "b": {
                "type": "string",
                "default": "2000-01-01",
                "pattern": "^\\d.*",
                "format": "date",
            },
        },
        "required": ["a"],
    }


@dataclasses.dataclass
class DcNumberAnnotated:
    a: t.Annotated[int, SchemaAnnotation(minimum=1, exclusive_maximum=11)]
    b: list[t.Annotated[int, SchemaAnnotation(minimum=0)]]
    c: t.Optional[t.Annotated[int, SchemaAnnotation(minimum=0)]]
    d: t.Annotated[
        float, SchemaAnnotation(maximum=12, exclusive_minimum=17, multiple_of=5)
    ] = 33.1


def test_get_schema_number_annotation():
    schema = get_schema(DcNumberAnnotated)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcNumberAnnotated",
        "properties": {
            "a": {"type": "integer", "minimum": 1, "exclusiveMaximum": 11},
            "b": {"type": "array", "items": {"type": "integer", "minimum": 0}},
            "c": {"anyOf": [{"type": "integer", "minimum": 0}, {"type": "null"}]},
            "d": {
                "type": "number",
                "default": 33.1,
                "maximum": 12,
                "exclusiveMinimum": 17,
                "multipleOf": 5,
            },
        },
        "required": ["a", "b", "c"],
    }


@dataclasses.dataclass
class DcDateTime:
    a: datetime.datetime
    b: datetime.date


def test_get_schema_date_time():
    schema = get_schema(DcDateTime)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcDateTime",
        "properties": {
            "a": {"type": "string", "format": "date-time"},
            "b": {"type": "string", "format": "date"},
        },
        "required": ["a", "b"],
    }


@dataclasses.dataclass
class DcAnnotatedBook:
    title: t.Annotated[str, SchemaAnnotation(title="Title")]


class DcAnnotatedAuthorHobby(enum.Enum):
    CHESS = "chess"
    SOCCER = "soccer"


@dataclasses.dataclass
class DcAnnotatedAuthor:
    name: t.Annotated[
        str,
        SchemaAnnotation(
            description="the name of the author", examples=["paul", "alice"]
        ),
    ]
    books: t.Annotated[
        list[DcAnnotatedBook],
        SchemaAnnotation(description="all the books the author has written"),
    ]
    hobby: t.Annotated[DcAnnotatedAuthorHobby, SchemaAnnotation(deprecated=True)]
    age: t.Annotated[
        t.Union[int, float], SchemaAnnotation(description="age in years")
    ] = 42


def test_get_schema_annotation():
    schema = get_schema(DcAnnotatedAuthor)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcAnnotatedAuthor",
        "properties": {
            "name": {
                "type": "string",
                "description": "the name of the author",
                "examples": ["paul", "alice"],
            },
            "books": {
                "type": "array",
                "items": {"$ref": "#/$defs/DcAnnotatedBook"},
                "description": "all the books the author has written",
            },
            "hobby": {
                "$ref": "#/$defs/DcAnnotatedAuthorHobby",
                "deprecated": True,
            },
            "age": {
                "anyOf": [{"type": "integer"}, {"type": "number"}],
                "default": 42,
                "description": "age in years",
            },
        },
        "required": ["name", "books", "hobby"],
        "$defs": {
            "DcAnnotatedBook": {
                "type": "object",
                "title": "DcAnnotatedBook",
                "properties": {"title": {"type": "string", "title": "Title"}},
                "required": ["title"],
            },
            "DcAnnotatedAuthorHobby": {
                "title": "DcAnnotatedAuthorHobby",
                "enum": ["chess", "soccer"],
            },
        },
    }


@dataclasses.dataclass
class DcSchemaConfigChild:
    a: int


@dataclasses.dataclass
class DcSchemaConfig:
    a: str
    child_1: DcSchemaConfigChild
    child_2: t.Annotated[DcSchemaConfigChild, SchemaAnnotation(title="2nd child")]
    friend: t.Annotated[DcSchemaConfig, SchemaAnnotation(title="a friend")]


def test_get_schema_config():
    schema = get_schema(DcSchemaConfig)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcSchemaConfig",
        "properties": {
            "a": {"type": "string"},
            "child_1": {"$ref": "#/$defs/DcSchemaConfigChild"},
            "child_2": {
                "$ref": "#/$defs/DcSchemaConfigChild",
                "title": "2nd child",
            },
            "friend": {"$ref": "#", "title": "a friend"},
        },
        "required": ["a", "child_1", "child_2", "friend"],
        "$defs": {
            "DcSchemaConfigChild": {
                "type": "object",
                "title": "DcSchemaConfigChild",
                "properties": {"a": {"type": "integer"}},
                "required": ["a"],
            }
        },
    }


@dataclasses.dataclass
class DcListAnnotation:
    a: t.Annotated[
        list[int], SchemaAnnotation(min_items=3, max_items=5, unique_items=True)
    ]
    b: t.Annotated[tuple[float, ...], SchemaAnnotation(min_items=3, max_items=10)] = ()


def test_get_schema_list_annotation():
    schema = get_schema(DcListAnnotation)
    print(schema)
    Draft202012Validator.check_schema(schema)
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": "DcListAnnotation",
        "properties": {
            "a": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 3,
                "maxItems": 5,
                "uniqueItems": True,
            },
            "b": {
                "type": "array",
                "items": {"type": "number"},
                "default": [],
                "minItems": 3,
                "maxItems": 10,
            },
        },
        "required": ["a"],
    }
