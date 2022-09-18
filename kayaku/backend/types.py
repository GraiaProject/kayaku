"""
This modules contains all shared and reausable types supporting style preservation.

Most of the time you won't have to instanciate them manually.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Generic, Iterable, List, Tuple, TypeVar, Union, overload

from typing_extensions import TypeAlias


class JSONType:
    """
    Base class for parsed types with style and metadata preservation.
    """

    json_before: list[WSC] = []
    """Whitespaces and comments sequence before the object."""
    json_after: list[WSC] = []
    """Whitespaces and comments sequence after the object."""

    def __post_init__(
        self,
        before: list[WSC | str] | None = None,
        after: list[WSC | str] | None = None,
    ):
        from . import wsc

        self.json_before = wsc.parse_list(before)
        self.json_after = wsc.parse_list(after)

    def __repr__(self) -> str:
        if attrs := getattr(self, "__dict__"):
            kwargs = ", ".join(f"{k}={v}" for k, v in attrs.items())
            return f"{self.__class__.__name__}({super().__repr__()}, {kwargs})"
        return f"{self.__class__.__name__}({super().__repr__()})"


class Container(JSONType):
    """
    Base class for containers with style and metadata preservation.
    """

    json_container_head: list[WSC] = []
    """Whitespaces and comments sequence in the head of the container."""
    json_container_tail: list[WSC] = []
    """Whitespaces and comments sequence in the tail of the container."""
    json_container_trailing_comma: bool = False
    """Wether this container have a trailing comma or not."""

    def __post_init__(
        self,
        before: list[WSC | str] | None = None,
        after: list[WSC | str] | None = None,
        head: list[WSC | str] | None = None,
        tail: list[WSC | str] | None = None,
        trailing_comma: bool = False,
    ):
        super().__post_init__(before=before, after=after)
        from . import wsc

        self.json_container_head = wsc.parse_list(head)
        self.json_container_tail = wsc.parse_list(tail)
        self.json_container_trailing_comma = trailing_comma


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

    pass


class LineStyleComment(Comment):
    """Stores a line-style comment (ie. starting with `//` and ending at the end of the current line)"""

    pass


class HashStyleComment(Comment):
    """Stores a hash-style comment (ie. starting with `#` and ending at the end of the current line)"""

    pass


class Object(dict, Container):
    """A JSON Object with order and style preservation"""

    pass


class Array(List["Value"], Container):
    """A JSON Array with style preservation"""

    def __post_init__(
        self,
        before: list[WSC | str] | None = None,
        after: list[WSC | str] | None = None,
        head: list[WSC | str] | None = None,
        tail: list[WSC | str] | None = None,
        trailing_comma: bool = False,
    ):
        Container.__post_init__(
            self,
            before=before,
            after=after,
            head=head,
            tail=tail,
            trailing_comma=trailing_comma,
        )


class Identifier(str, JSONType):
    "A quoteless string without special characters"
    pass


Ident = Identifier


class Quote(Enum):
    """Known quotes formats"""

    SINGLE = "'"
    DOUBLE = '"'


class String(str, JSONType):
    """A JSON String with style preservation"""

    quote: Quote = Quote.DOUBLE
    """Quote character wrapping the string"""

    linebreaks: list[int] = []
    """Escaped line breaks positions"""

    def __post_init__(
        self,
        quote: str | Quote = Quote.DOUBLE,
        linebreaks: list[int] | None = None,
        before: list[WSC | str] | None = None,
        after: list[WSC | str] | None = None,
    ):
        super().__post_init__(before=before, after=after)
        self.quote = Quote(quote) if isinstance(quote, str) else quote
        self.linebreaks = linebreaks or []


Key: TypeAlias = "String | Identifier | str"


class Number(JSONType):
    """
    Base class for all Number types and representations.
    """

    prefixed: bool = False
    """
    Is the number prefixed by an explicit sign
    """
    ...


class Integer(Number, int):
    """
    A JSON integer compatible with Python's `int`.
    """

    def __post_init__(
        self,
        prefixed: bool = False,
        before: list[WSC | str] | None = None,
        after: list[WSC | str] | None = None,
    ):
        self.prefixed = prefixed
        return super().__post_init__(before, after)

    def __str__(self) -> str:
        return int.__repr__(self)


class HexInteger(Integer):
    """
    A JSON integer compatible with Python's `int` and represented in its hexadecimal form.
    """

    def __str__(self) -> str:
        return hex(self)


class Float(Number, float):
    """
    A JSON float compatible with Python's `float`.
    """

    leading_point: bool
    significand: int | None

    def __post_init__(
        self,
        prefixed: bool = False,
        leading_point: bool = False,
        significand: int | None = None,
        before: list[WSC | str] | None = None,
        after: list[WSC | str] | None = None,
    ):
        self.prefixed = prefixed
        self.leading_point = leading_point
        self.significand = significand
        return super().__post_init__(before, after)

    def __str__(self) -> str:
        raw = float.__repr__(self)
        if self.leading_point and raw.startswith("0"):
            return raw[1:]
        if self.significand is not None:
            pos = raw.index(".") + 1
            raw = raw[: pos + self.significand]
        return raw


AnyNumber: TypeAlias = "Integer | Float"

T = TypeVar("T")


class Literal(JSONType, Generic[T]):
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


Value: TypeAlias = "Object | Array | String | Number | Literal | bool | None"
"""
A type alias matching the JSON Value.
"""

Member = Tuple[Key, Value]
"""
A Key-Value pair in an [Object][kayaku.backend.types.Object]
"""


class TupleWithTrailingComma(Tuple[T, ...]):
    trailing_comma: bool = False

    def __post_init__(self, trailing_comma: bool = False):
        self.trailing_comma = trailing_comma


@overload
def convert(obj: dict) -> Object:
    ...


@overload
def convert(obj: "list | tuple") -> Array:
    ...


@overload
def convert(obj: str) -> String:
    ...


@overload
def convert(obj: int) -> Integer:
    ...


@overload
def convert(obj: float) -> Float:
    ...


@overload
def convert(obj: "bool") -> Literal[bool]:
    ...


@overload
def convert(obj: None) -> Literal[None]:
    ...


def convert(obj: Any) -> JSONType:
    if isinstance(obj, JSONType):
        return obj
    if isinstance(obj, (list, tuple)):
        o = Array(obj)
    elif isinstance(obj, dict):
        o = Object(obj)
    elif isinstance(obj, str):
        o = String(obj)
    elif isinstance(obj, int):
        o = Integer(obj)
    elif isinstance(obj, float):
        o = Float(obj)
    elif isinstance(obj, bool):
        o = Literal(obj)
    elif obj is None:
        o = Literal(obj)
    else:
        raise TypeError(f"{obj} can't be automatically converted to JSONType!")
    o.__post_init__()
    return o
