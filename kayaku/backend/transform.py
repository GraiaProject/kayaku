from __future__ import annotations

import re
from typing import Any, cast

from lark.lexer import Token
from lark.visitors import Transformer as BaseTransformer
from lark.visitors import merge_transformers, v_args

from . import wsc
from .types import (  # noqa: F401
    WSC,
    Array,
    BlockStyleComment,
    Float,
    HashStyleComment,
    HexInteger,
    Identifier,
    Integer,
    JContainer,
    JLiteral,
    JNumber,
    JObject,
    JString,
    JType,
    LineStyleComment,
    Member,
    Quote,
    Value,
    WhiteSpace,
)


class WSCTransformer(BaseTransformer):
    """
    A [Transformer][lark.visitors.Transformer] handling whitespaces and comments.
    """

    @v_args(inline=True)
    def WS(self, token: Token) -> WhiteSpace:
        return WhiteSpace(token.value)

    def CPP_COMMENT(self, token: Token) -> LineStyleComment:
        return LineStyleComment(token.value[2:])

    def C_COMMENT(self, token: Token) -> BlockStyleComment:
        return BlockStyleComment(token.value[2:-2])

    def SH_COMMENT(self, token: Token) -> HashStyleComment:
        return HashStyleComment(token.value[1:])

    def wschs(self, wscs: list[WSC]) -> list[WSC]:
        return wscs

    def wscs(self, wscs: list[WSC]) -> list[WSC]:
        return wscs

    def ws(self, wscs: list[WSC]) -> list[WSC]:
        return wscs


class Transformer(BaseTransformer):
    """
    A [Transformer][lark.visitors.Transformer] for JSON5
    """

    @v_args(inline=True)
    def string(self, string: JString):
        return string

    @v_args(inline=True)
    def SINGLE_QUOTE_CHARS(self, token: Token) -> str:
        return (
            token.value.replace("\\/", "/")
            .encode()
            .decode("unicode_escape", "surrogatepass")
        )

    @v_args(inline=True)
    def DOUBLE_QUOTE_CHARS(self, token: Token) -> tuple[str, list[int]]:
        return token.value.replace("\\/", "/").encode().decode(
            "unicode_escape", "surrogatepass"
        ), [m.start() for m in re.finditer("\\\n", token.value)]

    @v_args(inline=True)
    def double_quote_string(
        self, string: tuple[str, list[int]] | None = None
    ) -> JString:
        value, linebreaks = string or ("", [])
        s = JString(value)
        s.__post_init__(quote=Quote.DOUBLE, linebreaks=linebreaks)
        return s

    @v_args(inline=True)
    def single_quote_string(self, string: str | None = None) -> JString:
        s = JString(string or "")
        s.__post_init__(quote=Quote.SINGLE)
        return s

    @v_args(inline=True)
    def IDENTIFIER_NAME(self, string) -> Identifier:
        return Identifier(string)

    @v_args(inline=True)
    def number(self, number: JNumber):
        return number

    def SIGNED_HEXNUMBER(self, token: Token):
        i = HexInteger(token.value, base=16)
        i.__post_init__(prefixed=token.value.startswith(("+", "-")))
        return i

    def SIGNED_NUMBER(self, token: Token):
        prefixed = token.value.startswith(("+", "-"))
        if (
            "." not in token.value
            and "e" not in token.value
            and token.value
            not in {"NaN", "+NaN", "-NaN", "+Infinity", "-Infinity", "Infinity"}
        ):
            i = Integer(token.value)
            i.__post_init__(prefixed=prefixed)
            return i
        significand = len(token.value.split(".")[1]) if "." in token.value else None
        f = Float(
            token.value,
        )
        f.__post_init__(
            prefixed=prefixed,
            leading_point=token.value.startswith("."),
            significand=significand,
        )
        return f

    @staticmethod
    def _set_trail(obj: JContainer, children: list) -> None:
        obj.json_container_tail = children[-2]
        obj.json_container_trailing_comma = (
            isinstance(children[-3], Token) and children[-3].value == ","
        )

    def object(self, children: list) -> Any:
        o = JObject(cast(Member, c) for c in children if isinstance(c, tuple))
        self._set_trail(o, children)
        return o

    def array(self, children: list) -> Any:
        a = Array(
            (cast(Value, value) for value in children if isinstance(value, JType))
        )
        self._set_trail(a, children)
        return a

    @v_args(inline=True)
    def literal(self, token: Token):
        if token.value == "true":
            return JLiteral[bool](True)
        elif token.value == "false":
            return JLiteral[bool](False)
        elif token.value == "null":
            return JLiteral[None](None)
        raise ValueError(f"Unknown literal: {token.value}")

    @v_args(inline=True)
    def pack_wsc(self, before: list[WSC], value: JType, after: list[WSC]) -> JType:
        value.json_before = before
        value.json_after = after
        return value

    value = pack_wsc
    key = pack_wsc

    pair = tuple


transformer = merge_transformers(Transformer(), wsc=wsc.transformer)