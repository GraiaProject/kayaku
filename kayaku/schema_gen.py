"""dataclass schema generator

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
import numbers
import re
import typing as t
from abc import ABC

import typing_extensions as t_e

from kayaku.doc_parse import store_field_description

_MISSING = dataclasses.MISSING


_Format = t.Literal[
    "date-time",
    "time",
    "date",
    "duration",
    "email",
    "idn-email",
    "hostname",
    "idn-hostname",
    "ipv4",
    "ipv6",
    "uuid",
    "uri",
    "uri-reference",
    "iri",
    "iri-reference",
    "regex",
]

SCHEMA_ANNO_KEY_MAP = {
    "min_length": "minLength",
    "max_length": "maxLength",
    "exclusive_minimum": "exclusiveMinimum",
    "exclusive_maximum": "exclusiveMaximum",
    "multiple_of": "multipleOf",
    "min_items": "minItems",
    "max_items": "maxItems",
    "unique_items": "uniqueItems",
}


@dataclasses.dataclass(frozen=True)
class Schema:
    title: t.Optional[str] = None
    description: t.Optional[str] = dataclasses.field(
        default=None, compare=False, hash=False
    )
    examples: t.Optional[list[t.Any]] = None
    deprecated: t.Optional[bool] = None

    def schema(self):
        return {
            SCHEMA_ANNO_KEY_MAP.get(k, k): v
            for k, v in dataclasses.asdict(self).items()
            if v is not None
        }


@dataclasses.dataclass(frozen=True)
class StringSchema(Schema):
    min_length: t.Optional[int] = None
    max_length: t.Optional[int] = None
    pattern: t.Optional[str] = None
    format: t.Optional[_Format] = None


@dataclasses.dataclass(frozen=True)
class NumberSchema(Schema):
    minimum: t.Optional[numbers.Number] = None
    maximum: t.Optional[numbers.Number] = None
    exclusive_minimum: t.Optional[numbers.Number] = None
    exclusive_maximum: t.Optional[numbers.Number] = None
    multiple_of: t.Optional[numbers.Number] = None


@dataclasses.dataclass(frozen=True)
class ContainerSchema(Schema):
    min_items: t.Optional[int] = None
    max_items: t.Optional[int] = None
    unique_items: t.Optional[bool] = None


# TODO: TypedDict
class ConfigModel(ABC):
    __dataclass_fields__: t.ClassVar[t.Dict[str, dataclasses.Field]]

    @classmethod
    def __subclasshook__(cls, oth):
        return isinstance(oth, type) and dataclasses.is_dataclass(oth)


def is_sub_type(sub: t.Any, parent: t.Any) -> bool:
    sub_origin = t_e.get_origin(sub) or sub
    return (
        isinstance(sub_origin, type)
        and issubclass(sub_origin, parent)
        or sub_origin == parent
    )


class SchemaGenerator:
    def __init__(self, dc: t.Type[ConfigModel] | None) -> None:
        self.root = dc
        self.seen_root = False
        self.defs = {}

    def retrieve_name(self, typ: t.Type) -> str:
        return f"{typ.__module__}.{typ.__qualname__}"

    def retrieve_title(self, typ: t.Type) -> str:
        return self.retrieve_name(typ)

    @classmethod
    def from_dc(cls, dc: t.Type[ConfigModel]) -> dict[str, t.Any]:
        generator = cls(dc)
        schema = generator.get_dc_schema(dc)
        if generator.defs:
            schema["$defs"] = generator.defs

        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **schema,
        }

    def get_dc_schema(self, dc: t.Type[ConfigModel]) -> dict[str, t.Any]:
        if dc == self.root:
            if self.seen_root:
                return {"$ref": "#"}
            self.seen_root = True
            schema = self.create_dc_schema(dc)
            return schema
        else:
            name = self.retrieve_name(dc)
            if name not in self.defs:
                schema = self.create_dc_schema(dc)
                self.defs[name] = schema
            return {
                "$ref": f"#/$defs/{name}",
            }

    def create_dc_schema(self, dc: t.Type[ConfigModel]):
        schema = {
            "type": "object",
            "title": self.retrieve_title(dc),
            "properties": {},
            "required": [],
        }
        store_field_description(dc, dc.__dataclass_fields__)
        type_hints = t_e.get_type_hints(dc, include_extras=True)
        for field in dataclasses.fields(dc):
            typ = type_hints[field.name]
            schema["properties"][field.name] = self.get_field_schema(typ, field.default)
            field_is_optional = (
                field.default is not _MISSING or field.default_factory is not _MISSING
            )
            if not field_is_optional:
                schema["required"].append(field.name)
        if not schema["required"]:
            schema.pop("required")
        return schema

    def get_field_schema(self, typ: t.Type, default: t.Any):
        if dataclasses.is_dataclass(typ):
            return self.get_dc_schema(typ)
        elif t_e.get_origin(typ) == t.Union:
            return self.get_union_schema(typ, default)
        elif t_e.get_origin(typ) == t.Literal:
            return self.get_literal_schema(typ, default)
        elif t_e.get_origin(typ) == t_e.Annotated:
            return self.get_annotated_schema(typ, default)
        elif typ == t.Any:
            return self.get_any_schema(default)
        elif is_sub_type(typ, dict):
            return self.get_dict_schema(typ)
        elif is_sub_type(typ, list):
            return self.get_list_schema(typ)
        elif is_sub_type(typ, tuple):
            return self.get_tuple_schema(typ, default)
        elif is_sub_type(typ, set):
            return self.get_set_schema(typ)
        elif typ is None or typ == type(None):
            return self.get_none_schema(default)
        elif is_sub_type(typ, str):
            return self.get_str_schema(default)
        elif is_sub_type(typ, bool):
            return self.get_bool_schema(default)
        elif is_sub_type(typ, int):
            return self.get_int_schema(default)
        elif is_sub_type(typ, numbers.Number):
            return self.get_number_schema(default)
        elif is_sub_type(typ, enum.Enum):
            return self.get_enum_schema(typ, default)
        elif is_sub_type(typ, datetime.datetime):
            return self.get_datetime_schema()
        elif is_sub_type(typ, datetime.date):
            return self.get_date_schema()
        elif is_sub_type(typ, re.Pattern):
            return self.get_regex_schema()
        raise NotImplementedError(f"field type '{typ}' not implemented")

    def get_any_schema(self, default: t.Any):
        return {} if default is _MISSING else {"default": default}

    def get_union_schema(self, typ: t.Type, default: t.Any):
        args = t_e.get_args(typ)
        if default is _MISSING:
            return {
                "anyOf": [self.get_field_schema(arg, _MISSING) for arg in args],
            }
        else:
            return {
                "anyOf": [self.get_field_schema(arg, _MISSING) for arg in args],
                "default": default,
            }

    def get_literal_schema(self, typ, default):
        schema = {} if default is _MISSING else {"default": default}
        args = t_e.get_args(typ)
        return {"enum": list(args), **schema}

    def get_dict_schema(self, typ):
        args = t_e.get_args(typ)
        assert len(args) in {0, 2}
        if args:
            assert args[0] == str
            return {
                "type": "object",
                "additionalProperties": self.get_field_schema(args[1], _MISSING),
            }
        else:
            return {"type": "object"}

    def get_list_schema(self, typ):
        args = t_e.get_args(typ)
        assert len(args) in {0, 1}
        if args:
            return {
                "type": "array",
                "items": self.get_field_schema(args[0], _MISSING),
            }
        else:
            return {"type": "array"}

    def get_tuple_schema(self, typ, default):
        schema = {} if default is _MISSING else {"default": list(default)}
        args = t_e.get_args(typ)
        if args and len(args) == 2 and args[1] is ...:
            schema = {
                "type": "array",
                "items": self.get_field_schema(args[0], _MISSING),
                **schema,
            }
        elif args:
            schema = {
                "type": "array",
                "prefixItems": [self.get_field_schema(arg, _MISSING) for arg in args],
                "minItems": len(args),
                "maxItems": len(args),
                **schema,
            }
        else:
            schema = {"type": "array", **schema}
        return schema

    def get_set_schema(self, typ):
        args = t_e.get_args(typ)
        assert len(args) in {0, 1}
        if args:
            return {
                "type": "array",
                "items": self.get_field_schema(args[0], _MISSING),
                "uniqueItems": True,
            }
        else:
            return {"type": "array", "uniqueItems": True}

    def get_none_schema(self, default):
        if default is _MISSING:
            return {"type": "null"}
        else:
            return {"type": "null", "default": default}

    def get_str_schema(self, default):
        if default is _MISSING:
            return {"type": "string"}
        else:
            return {"type": "string", "default": default}

    def get_bool_schema(self, default):
        if default is _MISSING:
            return {"type": "boolean"}
        else:
            return {"type": "boolean", "default": default}

    def get_int_schema(self, default):
        if default is _MISSING:
            return {"type": "integer"}
        else:
            return {"type": "integer", "default": default}

    def get_number_schema(self, default):

        if default is _MISSING:
            return {"type": "number"}
        else:
            return {"type": "number", "default": default}

    def get_enum_schema(self, typ: type[enum.Enum], default: enum.Enum):
        name = self.retrieve_name(typ)
        title = self.retrieve_title(typ)
        if name not in self.defs:
            self.defs[name] = {
                "title": title,
                "enum": [v.value for v in typ],
            }
        if default is _MISSING:
            return {
                "$ref": f"#/$defs/{name}",
            }
        else:
            return {
                "$ref": f"#/$defs/{name}",
                "default": default.value,
            }

    def get_annotated_schema(self, typ, default):
        args = t_e.get_args(typ)
        assert len(args) == 2
        base, annotation = args
        assert isinstance(annotation, Schema)
        if isinstance(annotation, StringSchema):
            if not is_sub_type(base, str):
                raise TypeError(f"Trying to apply string-specific annotation to {base}")
        elif isinstance(annotation, ContainerSchema):
            if not any(is_sub_type(base, typ) for typ in (list, tuple, set)):
                raise TypeError(
                    f"Trying to apply sequence-specific annotation to {base}"
                )
        elif isinstance(annotation, NumberSchema):
            if not (is_sub_type(base, numbers.Number) and base is not bool):
                raise TypeError(f"Trying to apply number-specific annotation to {base}")
        schema = self.get_field_schema(base, default)
        schema.update(annotation.schema())
        return schema

    def get_datetime_schema(self):
        return {"type": "string", "format": "date-time"}

    def get_date_schema(self):
        return {"type": "string", "format": "date"}

    def get_regex_schema(self):
        return {"type": "string", "format": "regex"}


def write_schema_ref(root: dict, sect: tuple[str, ...], name: str) -> None:
    for s in sect:
        root["type"] = "object"
        required: list[str] = root.setdefault("required", [])
        if s not in required:
            required.append(s)
        root = root.setdefault("properties", {})
        root = root.setdefault(s, {})

    all_of: list[dict[str, str]] = root.setdefault("allOf", [])
    if {"$ref": f"#/$defs/{name}"} not in all_of:
        all_of.append({"$ref": f"#/$defs/{name}"})


def gen_schema_from_list(
    models: list[tuple[tuple[str, ...], type[ConfigModel]]]
) -> dict[str, t.Any]:

    schemas = {}
    generator = SchemaGenerator(None)

    for sect, model in models:
        generator.get_dc_schema(model)  # preserve the model's schema in its `defs`
        write_schema_ref(schemas, sect, generator.retrieve_name(model))

    if generator.defs:
        schemas["$defs"] = generator.defs

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **schemas,
    }
