"""Prettify a JSON Container.
"""
from __future__ import annotations

import inspect
from typing import Literal as Constant
from typing import TypeVar

from .backend.types import (
    WSC,
    Array,
    BlockStyleComment,
    Comment,
    Identifier,
    JSONType,
    Object,
    Quote,
    String,
    WhiteSpace,
    convert,
)

T_Container = TypeVar("T_Container", Array, Object)

# FIXME: Full comment preservation


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

    @staticmethod
    def require_newline(wsc_list: list[WSC]) -> bool:
        res: bool = True
        for t in wsc_list:
            if isinstance(t, Comment):
                res |= isinstance(t, BlockStyleComment)
                break
            if "\n" in t:
                return True
            res = False
        return res

    def gen_comment_block(self, comment: str) -> BlockStyleComment:
        res = []
        for i in inspect.cleandoc(comment).splitlines():
            if i[:2] == "* ":
                res.append(i[2:])
            elif i == "*":
                res.append("")
            else:
                res.append(i)
        indentation: str = " " * self.layer * self.indent
        return BlockStyleComment(
            "".join(f"\n{indentation}* {i}" for i in res) + f"\n{indentation}"
        )

    def format_container(self, new_obj: T_Container, obj: T_Container) -> T_Container:
        comments = [i for i in obj.json_container_tail if isinstance(i, Comment)]
        newline = Prettifier.require_newline(obj.json_container_tail)
        new_obj.json_container_tail = self.format_wsc(comments, newline)
        return new_obj

    def format_wsc(self, comments: list[Comment], require_newline: bool) -> list[WSC]:
        indent: str = " " * self.layer * self.indent
        wsc_list: list[WSC] = []
        for comment in comments:
            wsc_list.extend(
                [
                    WhiteSpace(f"\n{indent}"),
                    self.gen_comment_block(comment)
                    if isinstance(comment, BlockStyleComment)
                    else comment,
                ]
            )
        if wsc_list and not require_newline:
            wsc_list[0] = WhiteSpace(" ")
        wsc_list.append(WhiteSpace(f"\n{indent}"))
        return wsc_list

    def convert_key(self, obj: String | Identifier | str) -> String | Identifier:
        if self.key_quote is None:
            return convert(obj)
        cls = String if self.key_quote else Identifier
        string = cls(obj)
        if hasattr(obj, "__dict__"):
            string.__dict__.update(obj.__dict__)
        return string

    def prettify_object(self, obj: Object) -> Object:
        """Prettify a JSON Object."""
        # Object(*(KVPair ,) container_trail)
        # KVPair(key : value)
        if not obj:
            return obj
        if len(obj) == 1 and not self.unfold_single:
            k, v = next(iter(obj.items()))
            k, v = self.convert_key(k), convert(v)
            sub_comments = self.collect_comments(k) + self.collect_comments(v)
            if not (
                sub_comments or (v and isinstance(v, (list, tuple, dict)))
            ):  # is simple type
                k.__json_clear__()
                v.__json_clear__()
                v.json_before.append(WhiteSpace(" "))
                return Object({k: v})
        self.layer += 1
        new_obj = Object()
        for k, v in obj.items():
            k, v = self.convert_key(k), convert(v)
            sub_comments = self.collect_comments(k) + self.collect_comments(v)
            newline = self.require_newline(k.json_before)
            k.__json_clear__()
            v.__json_clear__()
            if isinstance(v, (Array, Object)):
                v = self.prettify(v)
            v.json_before.append(WhiteSpace(" "))
            new_obj[k] = v
            k.json_before = self.format_wsc(sub_comments, newline)
        self.layer -= 1
        return self.format_container(new_obj, obj)

    def prettify_array(self, arr: Array) -> Array:
        """Prettify a JSON Array."""
        # Array(*(value ,) container_trail)
        if not arr:
            return arr
        if len(arr) == 1 and not self.unfold_single:
            v: JSONType = convert(arr[0])
            sub_comments = self.collect_comments(v)
            if not (
                sub_comments or (v and isinstance(v, (list, tuple, dict)))
            ):  # is simple type
                v.__json_clear__()
                return Array((v,))
        new_arr = Array()
        self.layer += 1
        for v in arr:
            v: JSONType = convert(v)
            sub_comments = self.collect_comments(v)
            newline = self.require_newline(v.json_before)
            v.__json_clear__()
            if isinstance(v, (Array, Object)):
                v = self.prettify(v)
            v.json_before = self.format_wsc(sub_comments, newline)
            new_arr.append(v)
        self.layer -= 1
        return self.format_container(new_arr, arr)

    def prettify(
        self, container: Object | Array, clean: bool = False
    ) -> Object | Array:
        if isinstance(container, Object):
            res = self.prettify_object(container)
        elif isinstance(container, Array):
            res = self.prettify_array(container)
        if clean:
            res.json_before.clear()
        return res
