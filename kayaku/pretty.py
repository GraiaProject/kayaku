"""Prettify a JSON Container.
"""
from __future__ import annotations

import inspect
from typing import Literal as Constant
from typing import TypeVar

import regex

from .backend.types import (
    WSC,
    Array,
    BlockStyleComment,
    Comment,
    Identifier,
    JObject,
    JString,
    JType,
    Quote,
    WhiteSpace,
    convert,
)

T_Container = TypeVar("T_Container", Array, JObject)

# LINK: https://262.ecma-international.org/5.1/#sec-7.6
IDENTIFIER_PATTERN = regex.compile(
    r"([\p{Lu}\p{Ll}\p{Lt}\p{Lm}\p{Lo}\p{Nl}$_]|\\u[0-9a-fA-F]{4})([\p{Lu}\p{Ll}\p{Lt}\p{Lm}\p{Lo}\p{Nl}$_\p{Mn}\p{Mc}\p{Nd}\p{Pc}\u200C\u200D]|\\u[0-9a-fA-F]{4})*".replace(
        r"\u200C", "\u200C"
    ).replace(
        r"\u200D", "\u200D"
    )
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
    def collect_comments(obj: JType) -> list[Comment]:
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

    @staticmethod
    def clean_comment(lines: list[str]) -> list[str]:
        res = []
        for i in lines:
            if i[:2] == "* ":
                res.append(i[2:])
            elif i == "*":
                res.append("")
            else:
                res.append(i)
        return res

    def gen_comment_block(self, comment: str) -> BlockStyleComment:
        lines: list[str] = inspect.cleandoc(comment).splitlines()
        if len(lines) <= 1:
            return BlockStyleComment(comment)
        lines = self.clean_comment(lines)
        indentation: str = " " * self.layer * self.indent
        return BlockStyleComment(
            "".join(f"\n{indentation}* {i}" for i in lines) + f"\n{indentation}"
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

    def convert_key(self, obj: JString | Identifier | str) -> JString | Identifier:
        if self.key_quote is None:
            return convert(obj)
        if self.key_quote:
            string = JString(obj).__post_init__(quote=self.key_quote)
        else:
            string = (
                Identifier(obj)
                if IDENTIFIER_PATTERN.fullmatch(obj)
                else JString(obj).__post_init__(Quote.DOUBLE)
            )
        obj = convert(obj)
        string.json_before = obj.json_before
        string.json_after = obj.json_after
        return string

    def prettify_object(self, obj: JObject) -> JObject:
        """Prettify a JSON Object."""
        # Object(*(KVPair ,) container_trail)
        # KVPair(key : value)
        if not obj and not obj.json_container_tail:
            return JObject().__post_init__()
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
                return JObject({k: v}).__post_init__()
        self.layer += 1
        new_obj = JObject().__post_init__()
        # Preserve container tail
        if obj and not obj.json_container_trailing_comma and (pair := obj.popitem()):
            k, v = self.convert_key(pair[0]), convert(pair[1])
            self.swap_tail(v, obj)
            obj[k] = v

        for k, v in obj.items():
            k, v = self.convert_key(k), convert(v)
            sub_comments = self.collect_comments(k) + self.collect_comments(v)
            newline = self.require_newline(k.json_before)
            k.__json_clear__()
            v.__json_clear__()
            if isinstance(v, (Array, JObject)):
                v = self.prettify(v)
            v.json_before.append(WhiteSpace(" "))
            new_obj[k] = v
            k.json_before = self.format_wsc(sub_comments, newline)
        self.layer -= 1
        return self.format_container(new_obj, obj)

    def prettify_array(self, arr: Array) -> Array:
        """Prettify a JSON Array."""
        # Array(*(value ,) container_trail)
        if not arr and not arr.json_container_tail:
            return Array().__post_init__()
        if len(arr) == 1 and not self.unfold_single:
            v: JType = convert(arr[0])
            sub_comments = self.collect_comments(v)
            if not (
                sub_comments or (v and isinstance(v, (list, tuple, dict)))
            ):  # is simple type
                v.__json_clear__()
                return Array((v,)).__post_init__()
        new_arr = Array().__post_init__()
        self.layer += 1
        # Preserve container tail
        if arr and not arr.json_container_trailing_comma:
            v = convert(arr.pop())
            self.swap_tail(v, arr)
            arr.append(v)
        for v in arr:
            v: JType = convert(v)
            sub_comments = self.collect_comments(v)
            newline = self.require_newline(v.json_before)
            v.__json_clear__()
            if isinstance(v, (Array, JObject)):
                v = self.prettify(v)
            v.json_before = self.format_wsc(sub_comments, newline)
            new_arr.append(v)
        self.layer -= 1
        return self.format_container(new_arr, arr)

    def swap_tail(self, v: JType, obj: Array | JObject) -> None:
        if any(isinstance(wsc, Comment) for wsc in v.json_after):
            obj.json_container_tail = v.json_after
            v.json_after = []

    def prettify(self, container: JObject | Array) -> JObject | Array:
        return (
            self.prettify_object(container)
            if isinstance(container, JObject)
            else self.prettify_array(container)
        )
