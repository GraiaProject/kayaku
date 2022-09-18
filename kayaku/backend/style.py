"""
This modules provides some helpers to handle style preservation.
"""

from __future__ import annotations

from typing import Any, Callable, cast

from lark.lexer import Token
from lark.visitors import Transformer, v_args

from . import wsc
from .types import (
    WSC,
    Array,
    JSONType,
    Key,
    Member,
    Object,
    TupleWithTrailingComma,
    Value,
)


class StylePreservingTransformer(Transformer):
    """
    A base [Transformer][lark.visitors.Transformer] with helpers to handle style preservation
    """

    @v_args(inline=True)
    def array(
        self,
        elements: TupleWithTrailingComma[Value],
        tail: list[WSC | str] | None = None,
    ) -> Array:
        a = Array(elements)
        a.__post_init__(
            tail=tail,
            trailing_comma=getattr(elements, "trailing_comma", False),
        )
        return a

    @v_args(inline=True)
    def value_list(self, *values) -> TupleWithTrailingComma[JSONType]:
        t = TupleWithTrailingComma[JSONType](
            (value for value in values if isinstance(value, JSONType)),
        )
        t.__post_init__(trailing_comma=isinstance(values[-1], Token))
        return t

    @v_args(inline=True)
    def object(
        self,
        members: TupleWithTrailingComma[Member],
        tail: list[WSC | str] | None = None,
        last=None,
    ) -> Object:
        o = Object(members)
        o.json_container_tail = wsc.parse_list(tail)
        return o

    @v_args(inline=True)
    def member_list(self, *members) -> TupleWithTrailingComma[Member]:
        t = TupleWithTrailingComma[Member](
            (cast(Member, member) for member in members if isinstance(member, tuple)),
        )
        t.__post_init__(trailing_comma=isinstance(members[-1], Token))
        return t

    def member(self, kv: list[Key | Value]) -> Member:
        assert len(kv) == 2
        return (cast(Key, kv[0]), cast(Value, kv[1]))

    @v_args(inline=True)
    def pack_wsc(
        self, before: list[WSC], value: JSONType, after: list[WSC]
    ) -> JSONType:
        value.json_before = before
        value.json_after = after
        return value

    value = pack_wsc
    key = pack_wsc


JSONEncoderMethod = Callable[[Any, Any], str]
"""A JSON encoder type method"""


def with_style(fn: JSONEncoderMethod) -> JSONEncoderMethod:
    """
    A decorator providing whitespaces and comments handling for encoders.

    It handles `json_before` and `json_after` serialization
    if the object to encode has these attributes.

    :param fn: An encoder method for a spcific type.
    """

    def encode_with_style(self, obj: Any) -> str:
        return "".join(
            (
                "".join(wsc.encode_wsc(w) for w in getattr(obj, "json_before", [])),
                fn(self, obj),
                "".join(wsc.encode_wsc(w) for w in getattr(obj, "json_after", [])),
            )
        )

    return encode_with_style
