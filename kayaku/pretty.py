"""Prettify a JSON Container.
"""
from __future__ import annotations

from typing import Literal as Constant

from .backend.types import (
    Array,
    Comment,
    Container,
    Identifier,
    JSONType,
    Object,
    Quote,
    String,
    WhiteSpace,
    convert,
)


class Prettifier:
    """JSON Container Prettifier.
    Comments inside a K-V pair is shifted to the key's before.
    """

    def __init__(
        self,
        indent: int = 4,
        trail_comma: bool = False,
        key_quote: Quote | None | Constant[False] = Quote.DOUBLE,
        string_quote: Quote | None = Quote.DOUBLE,
        unfold_single: bool = False,
    ):
        self.indent: int = indent
        self.trail_comma: bool = trail_comma
        self.key_quote: Quote | Constant[False] | None = key_quote
        self.string_quote: Quote | None = string_quote
        self.unfold_single: bool = unfold_single
        self.layer: int = 0

    @staticmethod
    def collect_comments(obj: JSONType) -> list[Comment]:
        return [i for i in obj.json_before + obj.json_after if isinstance(i, Comment)]

    def convert_key(self, obj: String | Identifier | str) -> String | Identifier:
        if self.key_quote is None:
            return convert(obj)
        elif self.key_quote is False:
            return Identifier(obj)
        string = String(obj)
        string.quote = self.key_quote
        return string

    def prettify_object(self, obj: Object) -> Object:  # type: ignore # FIXME
        """Prettify a JSON Object."""
        # Object(*(KVPair ,) container_trail)
        # KVPair(key : value)
        if not obj and not (comments := self.collect_comments(obj)):
            return obj
        if len(obj) == 1 and not self.unfold_single:
            k, v = next(iter(obj.items()))
            k, v = self.convert_key(k), convert(v)
            comments = self.collect_comments(k) + self.collect_comments(v)
            if not (comments or (v and isinstance(v, (list, tuple, dict)))):
                k.__json_clear__()
                v.__json_clear__()
                v.json_before.append(WhiteSpace(" "))
                return Object({k: v})

    def prettify_array(self, obj: Array) -> Array:  # type: ignore # FIXME
        """Prettify a JSON Array."""
        # Array(*(value ,) container_trail)
        if not obj and not (comments := self.collect_comments(obj)):
            return obj
        if len(obj) == 1 and not self.unfold_single:
            v = convert(obj[0])
            comments = self.collect_comments(v)
            if not (comments or (v and isinstance(v, (list, tuple, dict)))):
                v.__json_clear__()
                return Array((v,))

    def prettify(self, container: Container) -> Container:
        self.layer += 1
        if isinstance(container, Object):
            res = self.prettify_object(container)
        elif isinstance(container, Array):
            res = self.prettify_array(container)
        else:
            raise TypeError("Expected JSON container.")
        self.layer -= 1
        return res
