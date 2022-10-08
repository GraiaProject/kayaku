from __future__ import annotations

from typing import Any, Callable, TextIO

from . import wsc
from .types import AnyNumber, Float, Identifier, Integer, JNumber, JString, JWrapper

ESCAPES = {
    "\\": r"\\",
    "\n": r"\n",
    "\r": r"\r",
    "\b": r"\b",
    "\f": r"\f",
    "\t": r"\t",
    "\v": r"\v",
    "\0": r"\0",
    "\u2028": r"\\u2028",
    "\u2029": r"\\u2029",
}

JSONEncoderMethod = Callable[[Any, Any], None]
"""A JSON encoder type method"""


def with_style(fn: JSONEncoderMethod) -> JSONEncoderMethod:
    """
    A decorator providing whitespaces and comments handling for encoders.

    It handles `json_before` and `json_after` serialization
    if the object to encode has these attributes.

    :param fn: An encoder method for a spcific type.
    """

    def encode_with_style(self: Encoder, obj: Any) -> None:
        self.fp.write(
            "".join(wsc.encode_wsc(w) for w in getattr(obj, "json_before", [])),
        )
        fn(self, obj)
        self.fp.write(
            "".join(wsc.encode_wsc(w) for w in getattr(obj, "json_after", [])),
        )

    return encode_with_style


def escape_string(string: str, **escapes: str | int | None) -> str:
    out = string.translate(str.maketrans({**escapes, **ESCAPES}))
    if isinstance(string, JString):
        for line_break in string.linebreaks:
            out = out[: line_break - 1] + "\\\n" + out[line_break - 1 :]
    return out


class Encoder:
    def __init__(self, fp: TextIO):
        self.encode_func: dict[tuple[type, ...], Callable[[Any], None]] = {
            (JWrapper,): self.encode_wrapper,
            (bool, type(None)): self.encode_bool_like,
            (JNumber, int, float): self.encode_number,
            (str,): self.encode_string,
            (dict,): self.encode_dict,
            (list, tuple): self.encode_iterable,
        }
        self.fp = fp

    def encode(self, obj: Any) -> None:
        for typ_tuple, func in self.encode_func.items():
            if isinstance(obj, typ_tuple):
                func(obj)
                return
        raise NotImplementedError(f"Unknown type: {type(obj)}")

    @with_style
    def encode_wrapper(self, obj: JWrapper) -> None:
        return self.encode(obj.value)

    def encode_bool_like(self, obj: bool | None) -> None:
        self.fp.write({True: "true", False: "false", None: "null"}[obj])

    @with_style
    def encode_dict(self, obj: dict) -> None:
        self.fp.write("{")
        self.fp.write(
            "".join(wsc.encode_wsc(w) for w in getattr(obj, "json_container_head", []))
        )
        if obj:
            last_k = next(reversed(obj))
            for k, v in obj.items():
                self.encode_pair(k, v)
                if k is not last_k or getattr(
                    obj, "json_container_trailing_comma", False
                ):
                    self.fp.write(",")
        self.fp.write(
            "".join(wsc.encode_wsc(w) for w in getattr(obj, "json_container_tail", []))
        )
        self.fp.write("}")

    @with_style
    def encode_iterable(self, obj: list | tuple) -> None:
        self.fp.write("[")
        self.fp.write(
            "".join(wsc.encode_wsc(w) for w in getattr(obj, "json_container_head", []))
        )
        if obj:
            last_v = obj[-1]
            for v in obj:
                self.encode(v)
                if v is not last_v or getattr(
                    obj, "json_container_trailing_comma", False
                ):
                    self.fp.write(",")
        self.fp.write(
            "".join(wsc.encode_wsc(w) for w in getattr(obj, "json_container_tail", []))
        )
        self.fp.write("]")

    def encode_pair(self, key: str, value: Any) -> None:
        self.encode(key)
        self.fp.write(":")
        self.encode(value)

    @with_style
    def encode_number(self, obj: AnyNumber | int | float) -> None:
        if not isinstance(obj, JNumber):
            obj = (Integer if isinstance(obj, int) else Float)(obj)
        self.fp.write(obj.__round_dump__())

    @with_style
    def encode_string(self, obj: str) -> None:
        if isinstance(obj, JString):
            self.fp.write(f"{obj.quote.value}{escape_string(obj)}{obj.quote.value}")
        elif isinstance(obj, Identifier):
            self.fp.write(obj)
        else:
            self.fp.write(f'"{escape_string(obj)}"')
