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
import inspect
import numbers
import re
import typing as t

import typing_extensions as t_e

from .doc_parse import store_field_description
from .utils import DataClass, EmptyTypedDict, Unions, is_sub_type

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
    title: str | None = None
    description: str | None = None
    examples: list[t.Any] | None = None
    deprecated: bool | None = None

    def schema(self):
        return {
            SCHEMA_ANNO_KEY_MAP.get(k, k): v
            for k, v in dataclasses.asdict(self).items()
            if v is not None
        }


@dataclasses.dataclass(frozen=True)
class StringSchema(Schema):
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    format: _Format | None = None


@dataclasses.dataclass(frozen=True)
class NumberSchema(Schema):
    minimum: numbers.Number | None = None
    maximum: numbers.Number | None = None
    exclusive_minimum: numbers.Number | None = None
    exclusive_maximum: numbers.Number | None = None
    multiple_of: numbers.Number | None = None


@dataclasses.dataclass(frozen=True)
class ContainerSchema(Schema):
    min_items: int | None = None
    max_items: int | None = None
    unique_items: bool | None = None


class SchemaGenerator:
    def __init__(self, dc: type[DataClass] | None = None) -> None:
        self.root = dc
        self.seen_root = False
        self.defs = {}

    def retrieve_name(self, typ: type) -> str:
        return f"{typ.__module__}.{typ.__qualname__}"

    def retrieve_title(self, typ: type) -> str:
        return self.retrieve_name(typ)

    def format_docstring_description(
        self, field: dataclasses.Field, description: str
    ) -> str | None:
        return description

    @classmethod
    def from_dc(cls, dc: type[DataClass]) -> dict[str, t.Any]:
        generator = cls(dc)
        schema = generator.get_dc_schema(dc)
        if generator.defs:
            schema["$defs"] = generator.defs

        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **schema,
        }

    def get_dc_schema(self, dc: type[DataClass]) -> dict[str, t.Any]:
        if dc == self.root:
            if self.seen_root:
                return {"$ref": "#"}
            self.seen_root = True
            return self.create_dc_schema(dc)
        else:
            name = self.retrieve_name(dc)
            if name not in self.defs:
                schema = self.create_dc_schema(dc)
                self.defs[name] = schema
            return {
                "$ref": f"#/$defs/{name}",
            }

    def create_dc_schema(self, dc: type[DataClass]):
        schema = {
            "type": "object",
            "title": self.retrieve_title(dc),
            "properties": {},
            "required": [],
        }
        store_field_description(dc, dc.__dataclass_fields__)
        type_hints = t.get_type_hints(dc, include_extras=True)
        if (
            dc.__doc__ is not None
            and dc.__doc__
            != f"{dc.__name__}{str(inspect.signature(dc)).replace(' -> None', '')}"  # Ignore the generated __doc__
        ):
            schema["description"] = dc.__doc__
        for field in dataclasses.fields(dc):
            typ: t.Any = type_hints[field.name]
            if (f_description := field.metadata.get("description")) is not None:
                f_a: Schema
                base, f_a = (
                    t.get_args(typ)
                    if t.get_origin(typ) == t.Annotated
                    else (typ, Schema())
                )
                if f_a.description is None:
                    object.__setattr__(
                        f_a,
                        "description",
                        self.format_docstring_description(field, f_description),
                    )
                typ = t.Annotated[base, f_a]
            schema["properties"][field.name] = self.get_field_schema(typ, field.default)
            field_is_optional = (
                field.default is not _MISSING or field.default_factory is not _MISSING
            )
            if not field_is_optional:
                schema["required"].append(field.name)
        if not schema["required"]:
            schema.pop("required")
        return schema

    def get_simple_schema(self, typ: type, default: t.Any):
        if typ is t.Any:
            return self.get_any_schema(default)
        elif typ in (None, type(None)):
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

    def get_complex_schema(self, typ: type, default: t.Any):
        if dataclasses.is_dataclass(typ):
            return self.get_dc_schema(typ)
        elif t.get_origin(typ) in Unions:
            return self.get_union_schema(typ, default)
        elif t.get_origin(typ) == t.Literal:
            return self.get_literal_schema(typ, default)
        elif t.get_origin(typ) == t.Annotated:
            return self.get_annotated_schema(typ, default)
        elif t.is_typeddict(typ) or t_e.is_typeddict(typ):
            return self.get_typed_dict_schema(typ)
        elif is_sub_type(typ, dict):
            return self.get_dict_schema(typ)
        elif is_sub_type(typ, list):
            return self.get_list_schema(typ)
        elif is_sub_type(typ, tuple):
            return self.get_tuple_schema(typ, default)
        elif is_sub_type(typ, set):
            return self.get_set_schema(typ)

    def get_field_schema(self, typ: type, default: t.Any):
        if (schema := self.get_simple_schema(typ, default)) is not None:
            return schema
        if (schema := self.get_complex_schema(typ, default)) is not None:
            return schema
        raise NotImplementedError(f"field type '{typ}' not implemented")

    def get_any_schema(self, default: t.Any):
        return {} if default is _MISSING else {"default": default}

    def get_union_schema(self, typ: type, default: t.Any):
        args = t.get_args(typ)
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
        args = t.get_args(typ)
        return {"enum": list(args), **schema}

    def get_dict_schema(self, typ):
        args = t.get_args(typ)
        assert len(args) in {0, 2}
        if args:
            assert args[0] is str
            return {
                "type": "object",
                "additionalProperties": self.get_field_schema(args[1], _MISSING),
            }
        else:
            return {"type": "object"}

    def get_typed_dict_schema(self, typ: type[EmptyTypedDict]):
        fields: list[tuple[str, t.Any]] = []
        required: list[str] = []  # Python 3.8- don't have `__required_keys__`
        for name, anno in t_e.get_type_hints(typ, include_extras=True).items():
            anno: t.Any
            schema_anno: Schema | None = None
            if t_e.get_origin(anno) == t_e.Annotated:
                anno, schema_anno = t_e.get_args(anno)
            if (
                t_e.get_origin(anno) == t_e.Required
                or typ.__total__
                and t_e.get_origin(anno) != t_e.NotRequired
            ):
                required.append(name)
            if t_e.get_origin(anno) in (t_e.Required, t_e.NotRequired):
                anno = t_e.get_args(anno)[0]
            fields.append(
                (
                    name,
                    (anno if schema_anno is None else t.Annotated[anno, schema_anno]),
                )
            )
        dc: type[DataClass] = t.cast(
            type[DataClass], dataclasses.make_dataclass(typ.__qualname__, fields)
        )
        dc.__module__ = typ.__module__
        store_field_description(typ, dc.__dataclass_fields__)
        dc_schema = self.get_dc_schema(dc)
        dc_def = self.defs[self.retrieve_name(dc)]
        dc_def["required"] = required
        return dc_schema

    def get_list_schema(self, typ):
        args = t.get_args(typ)
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
        args = t.get_args(typ)
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
        args = t.get_args(typ)
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
        args = t.get_args(typ)
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
        elif (
            isinstance(annotation, NumberSchema)
            and not is_sub_type(base, numbers.Number)
            and base is bool
        ):
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


def update_schema_ref(root: dict, sect: tuple[str, ...], name: str) -> None:
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
