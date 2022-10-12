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
class SchemaAnnotation:
    title: t.Optional[str] = None
    description: t.Optional[str] = None
    examples: t.Optional[list[t.Any]] = None
    deprecated: t.Optional[bool] = None
    min_length: t.Optional[int] = None
    max_length: t.Optional[int] = None
    pattern: t.Optional[str] = None
    format: t.Optional[_Format] = None
    minimum: t.Optional[numbers.Number] = None
    maximum: t.Optional[numbers.Number] = None
    exclusive_minimum: t.Optional[numbers.Number] = None
    exclusive_maximum: t.Optional[numbers.Number] = None
    multiple_of: t.Optional[numbers.Number] = None
    min_items: t.Optional[int] = None
    max_items: t.Optional[int] = None
    unique_items: t.Optional[bool] = None

    def schema(self):
        return {
            SCHEMA_ANNO_KEY_MAP.get(k, k): v
            for k, v in dataclasses.asdict(self).items()
            if v is not None
        }


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
    def from_dc(cls, dc: t.Type[ConfigModel]):
        generator = cls(dc)
        schema = generator.get_dc_schema(dc, SchemaAnnotation())
        if generator.defs:
            schema["$defs"] = generator.defs

        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **schema,
        }

    def get_dc_schema(self, dc: t.Type[ConfigModel], annotation: SchemaAnnotation):
        if dc == self.root:
            if self.seen_root:
                return {"$ref": "#", **annotation.schema()}
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
                **annotation.schema(),
            }

    def create_dc_schema(self, dc: t.Type[ConfigModel]):
        schema = {
            "type": "object",
            "title": self.retrieve_title(dc),
            "properties": {},
            "required": [],
        }
        type_hints = t_e.get_type_hints(dc, include_extras=True)
        for field in dataclasses.fields(dc):
            type_ = type_hints[field.name]
            schema["properties"][field.name] = self.get_field_schema(
                type_, field.default, SchemaAnnotation()
            )
            field_is_optional = (
                field.default is not _MISSING or field.default_factory is not _MISSING
            )
            if not field_is_optional:
                schema["required"].append(field.name)
        if not schema["required"]:
            schema.pop("required")
        return schema

    def get_field_schema(
        self, typ: t.Type, default: t.Any, annotation: SchemaAnnotation
    ):
        if dataclasses.is_dataclass(typ):
            return self.get_dc_schema(typ, annotation)
        elif t_e.get_origin(typ) == t.Union:
            return self.get_union_schema(typ, default, annotation)
        elif t_e.get_origin(typ) == t.Literal:
            return self.get_literal_schema(typ, default, annotation)
        elif t_e.get_origin(typ) == t_e.Annotated:
            return self.get_annotated_schema(typ, default)
        elif typ == t.Any:
            return self.get_any_schema(default, annotation)
        elif is_sub_type(typ, dict):
            return self.get_dict_schema(typ, annotation)
        elif is_sub_type(typ, list):
            return self.get_list_schema(typ, annotation)
        elif is_sub_type(typ, tuple):
            return self.get_tuple_schema(typ, default, annotation)
        elif is_sub_type(typ, set):
            return self.get_set_schema(typ, annotation)
        elif typ is None or typ == type(None):
            return self.get_none_schema(default, annotation)
        elif is_sub_type(typ, str):
            return self.get_str_schema(default, annotation)
        elif is_sub_type(typ, bool):
            return self.get_bool_schema(default, annotation)
        elif is_sub_type(typ, int):
            return self.get_int_schema(default, annotation)
        elif is_sub_type(typ, numbers.Number):
            return self.get_number_schema(default, annotation)
        elif is_sub_type(typ, enum.Enum):
            return self.get_enum_schema(typ, default, annotation)
        elif is_sub_type(typ, datetime.datetime):
            return self.get_datetime_schema(annotation)
        elif is_sub_type(typ, datetime.date):
            return self.get_date_schema(annotation)
        elif is_sub_type(typ, re.Pattern):
            return self.get_regex_schema(annotation)
        raise NotImplementedError(f"field type '{typ}' not implemented")

    def get_any_schema(self, default: t.Any, annotation: SchemaAnnotation):
        if default is _MISSING:
            return {
                **annotation.schema(),
            }
        else:
            return {
                "default": default,
                **annotation.schema(),
            }

    def get_union_schema(
        self, typ: t.Type, default: t.Any, annotation: SchemaAnnotation
    ):
        args = t_e.get_args(typ)
        if default is _MISSING:
            return {
                "anyOf": [
                    self.get_field_schema(arg, _MISSING, SchemaAnnotation())
                    for arg in args
                ],
                **annotation.schema(),
            }
        else:
            return {
                "anyOf": [
                    self.get_field_schema(arg, _MISSING, SchemaAnnotation())
                    for arg in args
                ],
                "default": default,
                **annotation.schema(),
            }

    def get_literal_schema(self, type_, default, annotation: SchemaAnnotation):
        if default is _MISSING:
            schema = {**annotation.schema()}
        else:
            schema = {"default": default, **annotation.schema()}
        args = t_e.get_args(type_)
        return {"enum": list(args), **schema}

    def get_dict_schema(self, type_, annotation: SchemaAnnotation):
        args = t_e.get_args(type_)
        assert len(args) in {0, 2}
        if args:
            assert args[0] == str
            return {
                "type": "object",
                "additionalProperties": self.get_field_schema(
                    args[1], _MISSING, SchemaAnnotation()
                ),
                **annotation.schema(),
            }
        else:
            return {"type": "object", **annotation.schema()}

    def get_list_schema(self, type_, annotation: SchemaAnnotation):
        args = t_e.get_args(type_)
        assert len(args) in {0, 1}
        if args:
            return {
                "type": "array",
                "items": self.get_field_schema(args[0], _MISSING, SchemaAnnotation()),
                **annotation.schema(),
            }
        else:
            return {"type": "array", **annotation.schema()}

    def get_tuple_schema(self, type_, default, annotation: SchemaAnnotation):
        if default is _MISSING:
            schema = {**annotation.schema()}
        else:
            schema = {"default": list(default), **annotation.schema()}
        args = t_e.get_args(type_)
        if args and len(args) == 2 and args[1] is ...:
            schema = {
                "type": "array",
                "items": self.get_field_schema(args[0], _MISSING, SchemaAnnotation()),
                **schema,
            }
        elif args:
            schema = {
                "type": "array",
                "prefixItems": [
                    self.get_field_schema(arg, _MISSING, SchemaAnnotation())
                    for arg in args
                ],
                "minItems": len(args),
                "maxItems": len(args),
                **schema,
            }
        else:
            schema = {"type": "array", **schema}
        return schema

    def get_set_schema(self, type_, annotation: SchemaAnnotation):
        args = t_e.get_args(type_)
        assert len(args) in {0, 1}
        if args:
            return {
                "type": "array",
                "items": self.get_field_schema(args[0], _MISSING, SchemaAnnotation()),
                "uniqueItems": True,
                **annotation.schema(),
            }
        else:
            return {"type": "array", "uniqueItems": True, **annotation.schema()}

    def get_none_schema(self, default, annotation: SchemaAnnotation):
        if default is _MISSING:
            return {"type": "null", **annotation.schema()}
        else:
            return {"type": "null", "default": default, **annotation.schema()}

    def get_str_schema(self, default, annotation: SchemaAnnotation):
        if default is _MISSING:
            return {"type": "string", **annotation.schema()}
        else:
            return {"type": "string", "default": default, **annotation.schema()}

    def get_bool_schema(self, default, annotation: SchemaAnnotation):
        if default is _MISSING:
            return {"type": "boolean", **annotation.schema()}
        else:
            return {"type": "boolean", "default": default, **annotation.schema()}

    def get_int_schema(self, default, annotation: SchemaAnnotation):
        if default is _MISSING:
            return {"type": "integer", **annotation.schema()}
        else:
            return {"type": "integer", "default": default, **annotation.schema()}

    def get_number_schema(self, default, annotation: SchemaAnnotation):

        if default is _MISSING:
            return {"type": "number", **annotation.schema()}
        else:
            return {"type": "number", "default": default, **annotation.schema()}

    def get_enum_schema(
        self, type_: type[enum.Enum], default, annotation: SchemaAnnotation
    ):
        name = self.retrieve_name(type_)
        title = self.retrieve_title(type_)
        if name not in self.defs:
            self.defs[name] = {
                "title": title,
                "enum": [v.value for v in type_],
            }
        if default is _MISSING:
            return {
                "$ref": f"#/$defs/{name}",
                **annotation.schema(),
            }
        else:
            return {
                "$ref": f"#/$defs/{name}",
                "default": default.value,
                **annotation.schema(),
            }

    def get_annotated_schema(self, type_, default):
        args = t_e.get_args(type_)
        assert len(args) == 2
        return self.get_field_schema(args[0], default, args[1])

    def get_datetime_schema(self, annotation: SchemaAnnotation):
        return {"type": "string", "format": "date-time", **annotation.schema()}

    def get_date_schema(self, annotation: SchemaAnnotation):
        return {"type": "string", "format": "date", **annotation.schema()}

    def get_regex_schema(self, annotation: SchemaAnnotation):
        return {"type": "string", "format": "regex", **annotation.schema()}


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
        generator.get_dc_schema(
            model, SchemaAnnotation()
        )  # preserve the model's schema in its `defs`
        write_schema_ref(schemas, sect, generator.retrieve_name(model))

    if generator.defs:
        schemas["$defs"] = generator.defs

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **schemas,
    }
