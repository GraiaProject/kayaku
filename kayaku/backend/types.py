"""
This modules contains all shared and reusable types supporting style preservation.

Most of the time you won't have to instantiate them manually.
"""

from __future__ import annotations

import enum
import math
import re
from datetime import date, datetime, time
from enum import Enum
from typing import Any, Generic, List, Tuple, TypeVar, overload

from typing_extensions import Self, TypeAlias


class JType:
    """
    Base class for parsed types with style and metadata preservation.
    """

    json_before: list[WSC] = []
    """Whitespaces and comments sequence before the object."""
    json_after: list[WSC] = []
    """Whitespaces and comments sequence after the object."""

    def __post_init__(self) -> Self:
        self.json_before = []
        self.json_after = []
        return self

    def __repr__(self) -> str:
        if attrs := getattr(self, "__dict__"):
            kwargs = ", ".join(f"{k}={v}" for k, v in attrs.items())
            return f"{self.__class__.__name__}({super().__repr__()}, {kwargs})"
        return f"{self.__class__.__name__}({super().__repr__()})"

    def __json_clear__(self):
        self.json_before = []
        self.json_after = []


class JContainer(JType):
    """
    Base class for containers with style and metadata preservation.
    """

    json_container_tail: list[WSC] = []
    """Whitespaces and comments sequence in the tail of the container."""
    json_container_trailing_comma: bool = False
    """Wether this container have a trailing comma or not."""

    def __post_init__(
        self,
        tail: list[WSC] | None = None,
        trailing_comma: bool = False,
    ) -> Self:
        super().__post_init__()

        self.json_container_tail = tail or []
        self.json_container_trailing_comma = trailing_comma
        return self


class WhiteSpace(str):
    """Stores a sequence of whitespaces"""

    def __repr__(self) -> str:
        return f"WhiteSpace({super().__repr__()})"


class Comment(str):
    """Store a comment"""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({super().__repr__()})"


WSC: TypeAlias = "WhiteSpace | Comment"
"""A whitespace or a comment"""


class BlockStyleComment(Comment):
    """Stores a block-style comment (ie. starting with `/*` and ending with `*/`)"""


class LineStyleComment(Comment):
    """Stores a line-style comment (ie. starting with `//` and ending at the end of the current line)"""


class JObject(JContainer, dict):
    """A JSON Object with order and style preservation"""


T = TypeVar("T")


class Array(JContainer, List[T]):
    """A JSON Array with style preservation"""


class Identifier(JType, str):
    "A quoteless string without special characters"

    def __repr__(self) -> str:
        if attrs := getattr(self, "__dict__"):
            kwargs = ", ".join(f"{k}={v}" for k, v in attrs.items())
            return f"{self.__class__.__name__}({super().__repr__()}, {kwargs})"
        return f"{self.__class__.__name__}({super().__repr__()})"


Ident = Identifier


class Quote(Enum):
    """Known quotes formats"""

    SINGLE = "'"
    DOUBLE = '"'


class JString(JType, str):
    """A JSON String with style preservation"""

    quote: Quote = Quote.DOUBLE
    """Quote character wrapping the string"""

    linebreaks: list[int] = []
    """Escaped line breaks positions"""

    def __post_init__(
        self,
        quote: str | Quote = Quote.DOUBLE,
        linebreaks: list[int] | None = None,
    ) -> Self:
        super().__post_init__()
        self.quote = Quote(quote) if isinstance(quote, str) else quote
        self.linebreaks = linebreaks or []
        return self

    def __repr__(self) -> str:
        if attrs := getattr(self, "__dict__"):
            kwargs = ", ".join(f"{k}={v}" for k, v in attrs.items())
            return f"{self.__class__.__name__}({self.quote.value}{self}{self.quote.value}, {kwargs})"
        return f"{self.__class__.__name__}({super().__repr__()})"


Key: TypeAlias = "JString | Identifier | str"


class JNumber(JType):
    """
    Base class for all Number types and representations.
    """

    origin: str | None = None

    def __post_init__(self, origin: str | None = None) -> Self:
        self.origin = origin
        return super().__post_init__()

    def __round_dump__(self) -> str:
        ...


class Integer(JNumber, int):
    """
    A JSON integer compatible with Python's `int`.
    """

    def __str__(self) -> str:
        return int.__repr__(self)

    def __round_dump__(self) -> str:
        if self.origin and int(self.origin) == self:
            return self.origin

        return int.__repr__(self)


class HexInteger(Integer):
    """
    A JSON integer compatible with Python's `int` and represented in its hexadecimal form.
    """

    def __str__(self) -> str:
        return hex(self)

    def __round_dump__(self) -> str:
        if self.origin and int(self.origin, base=16) == self:
            return self.origin

        return hex(self)


class Float(JNumber, float):
    """
    A JSON float compatible with Python's `float`.
    """

    def __round_dump__(self) -> str:
        if self.origin:
            constructed = float(self.origin)
            if (math.isnan(constructed) and math.isnan(self)) or self == constructed:
                return self.origin

        return float.__repr__(self).replace("nan", "NaN").replace("inf", "Infinity")


AnyNumber: TypeAlias = "Integer | Float"

T = TypeVar("T")


class JWrapper(JType, Generic[T]):
    """
    Represents a JSON Literal and wraps the equivalent value in Python.
    """

    value: T
    """
    The Python equivalent value.
    """

    def __init__(self, value: T) -> None:
        self.value = value

    def __eq__(self, obj: object) -> bool:
        return self.value.__eq__(obj)

    def __hash__(self) -> int:
        return self.value.__hash__()


Value: TypeAlias = "JObject | Array | JString | JNumber | JWrapper | bool | None"
"""
A type alias matching the JSON Value.
"""

Member = Tuple[Key, Value]
"""
A Key-Value pair in an [Object][kayaku.backend.types.Object]
"""


class TupleWithTrailingComma(Tuple[T, ...]):
    trailing_comma: bool = False

    def __post_init__(self, trailing_comma: bool = False) -> Self:
        self.trailing_comma = trailing_comma
        return Self


JSONType_T = TypeVar("JSONType_T", bound=JType)


@overload
def convert(obj: dict) -> JObject:
    ...


@overload
def convert(obj: "list | tuple") -> Array:
    ...


@overload
def convert(obj: str) -> JString:
    ...


@overload
def convert(obj: int) -> Integer:
    ...


@overload
def convert(obj: float) -> Float:
    ...


@overload
def convert(obj: "bool") -> JWrapper[bool]:
    ...


@overload
def convert(obj: None) -> JWrapper[None]:
    ...


@overload
def convert(obj: JSONType_T) -> JSONType_T:
    ...


def convert(obj: Any) -> JType:
    if isinstance(obj, JType):
        return obj
    if isinstance(obj, (list, tuple)):
        o = Array(obj)
    elif isinstance(obj, dict):
        o = JObject(obj)
    elif isinstance(obj, str):
        o = JString(obj)
    elif isinstance(obj, int):
        o = Integer(obj)
    elif isinstance(obj, float):
        o = Float(obj)
    elif (
        isinstance(obj, (bool, date, time, datetime, re.Pattern, enum.Enum))
        or obj == None
    ):
        o = JWrapper(obj)
    else:
        raise TypeError(f"{obj} can't be automatically converted to JSONType!")
    o.__post_init__()
    return o
