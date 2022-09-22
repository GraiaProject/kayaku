from __future__ import annotations

from typing import Any

from . import wsc
from .style import with_style
from .types import AnyNumber, Identifier, JLiteral, JNumber, JString  # noqa: F401

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


def escape_string(string: str, **escapes: str | int | None) -> str:
    out = string.translate(str.maketrans({**escapes, **ESCAPES}))
    if isinstance(string, JString):
        for line_break in string.linebreaks:
            out = out[: line_break - 1] + "\\\n" + out[line_break - 1 :]
    return out


class Encoder:
    def encode(self, obj: Any) -> str:
        if isinstance(obj, JNumber):
            return self.encode_number(obj)
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
        if isinstance(obj, JLiteral):
            return self.encode_literal(obj)
        raise NotImplementedError(f"Unknown type: {type(obj)}")

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
    def encode_literal(self, obj: JLiteral) -> str:
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
                "," if getattr(obj, "json_container_trailing_comma", False) else "",
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
                "," if getattr(obj, "json_container_trailing_comma", False) else "",
                "".join(
                    wsc.encode_wsc(w) for w in getattr(obj, "json_container_tail", [])
                ),
                "]",
            )
        )

    def encode_pair(self, key: str, value: Any) -> str:
        return f"{self.encode(key)}:{self.encode(value)}"

    @with_style
    def encode_number(self, obj: AnyNumber) -> str:
        presentation: str = {
            float("inf"): "Infinity",
            float("-inf"): "-Infinity",
            float("NaN"): "NaN",
        }.get(obj, str(obj))
        return f"+{presentation}" if obj > 0 and obj.prefixed else presentation

    @with_style
    def encode_string(self, obj: str) -> str:
        if isinstance(obj, JString):
            return f"{obj.quote.value}{escape_string(obj)}{obj.quote.value}"
        elif isinstance(obj, Identifier):
            return obj
        return f'"{escape_string(obj)}"'


encoder = Encoder()
