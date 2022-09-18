"""
This module implements the [JSONModule protocol][kayaku.backend.protocol.JSONModule]
for [JSON](https://www.json.org/).

While [JSON](https://www.json.org/) is natively supported by Python standard library,
the builtin module doesn't provide style preservation.

This one do by returning [style preserving types][kayaku.backend.types] storing whitespaces.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lark.lexer import Token
from lark.visitors import merge_transformers, v_args

from . import protocol, wsc
from .style import StylePreservingTransformer, with_style
from .types import Float, Integer, Literal, String  # noqa: F401


class JSONTransformer(StylePreservingTransformer):
    """
    A [Transformer][lark.visitors.Transformer] for JSON
    """

    @v_args(inline=True)
    def string(self, s):
        return String(
            s[1:-1]
            .replace("\\/", "/")
            .encode()
            .decode("unicode_escape", "surrogatepass")
        )

    @v_args(inline=True)
    def float_literal(self, literal: str):
        return Float(literal)

    @v_args(inline=True)
    def number(self, num: str):
        return Float(num) if "." in num or "e" in num else Integer(num)

    @v_args(inline=True)
    def literal(self, token: Token):
        if token.value == "true":
            return Literal[bool](True)
        elif token.value == "false":
            return Literal[bool](False)
        elif token.value == "null":
            return Literal[None](None)
        raise ValueError(f"Unknown literal: {token.value}")


transformer = merge_transformers(JSONTransformer(), wsc=wsc.transformer)


class JSONEncoder(protocol.Encoder):
    """
    The default JSON Encoder
    """

    def encode(self, obj: Any) -> str:
        if isinstance(obj, bool):
            return self.encode_bool(obj)
        if isinstance(obj, str):
            return self.encode_string(obj)
        if isinstance(obj, int):
            return self.encode_int(obj)
        if isinstance(obj, float):
            return self.encode_float(obj)
        if isinstance(obj, dict):
            return self.encode_dict(obj)
        if isinstance(obj, (list, tuple)):
            return self.encode_iterable(obj)
        if isinstance(obj, Literal):
            return self.encode_literal(obj)
        raise NotImplementedError(f"Unknown type: {type(obj)}")

    @with_style
    def encode_string(self, obj: str) -> str:
        return f'"{obj}"'

    @with_style
    def encode_int(self, obj: int) -> str:
        return str(obj)

    @with_style
    def encode_float(self, obj: float) -> str:
        return str(obj)

    @with_style
    def encode_bool(self, obj: bool) -> str:
        return "true" if obj else "false"

    @with_style
    def encode_literal(self, obj: Literal) -> str:
        if obj.value is True:
            return "true"
        if obj.value is False:
            return "false"
        if obj.value is None:
            return "null"
        raise NotImplementedError(f"Unknown literal: {obj.value}")

    @with_style
    def encode_dict(self, obj: dict) -> str:
        return "".join(
            (
                "{",
                "".join(
                    wsc.encode_wsc(w) for w in getattr(obj, "json_container_head", [])
                ),
                ",".join(self.encode_pair(k, v) for k, v in obj.items()),
                "," if getattr(obj, "json_container_trailing_coma", False) else "",
                "".join(
                    wsc.encode_wsc(w) for w in getattr(obj, "json_container_tail", [])
                ),
                "}",
            )
        )

    @with_style
    def encode_iterable(self, obj: list | tuple) -> str:
        return "".join(
            (
                "[",
                "".join(
                    wsc.encode_wsc(w) for w in getattr(obj, "json_container_head", [])
                ),
                ",".join(self.encode(item) for item in obj),
                "," if getattr(obj, "json_container_trailing_coma", False) else "",
                "".join(
                    wsc.encode_wsc(w) for w in getattr(obj, "json_container_tail", [])
                ),
                "]",
            )
        )

    def encode_pair(self, key: str, value: Any) -> str:
        return f"{self.encode(key)}:{self.encode(value)}"


@dataclass
class FormatOptions:
    trim_whitespaces: bool = False
    keep_newlines: bool = False
    add_end_line_return: bool = True


# parser, loads, load, dumps, dump = protocol.factory("json", transformer, JSONEncoder, lexer="basic")


protocol.implement("json", transformer, JSONEncoder, lexer="basic")
