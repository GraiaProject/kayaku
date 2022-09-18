"""
This module provides supprot for the `JSONC` file format

This is a format introduced by
[github/Microsoft in VSCode](https://code.visualstudio.com/docs/languages/json#_json-with-comments).
This is basically standard JSON with both line and block comments
supports as well as optionnal trailing coma support.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from lark.visitors import merge_transformers

from . import json, protocol, wsc
from .style import StylePreservingTransformer
from .types import WSC, Array, Float, Integer, JSONType, Object, String  # noqa: F401

Member = Tuple[String, JSONType]


class JSONCTransformer(StylePreservingTransformer):
    """
    A [Transformer][lark.visitors.Transformer] for JSONC aka. JSON with Comments
    """

    pass


transformer = merge_transformers(
    JSONCTransformer(), json=json.transformer, wsc=wsc.transformer
)


class JSONCEncoder(json.JSONEncoder):
    pass


@dataclass
class FormatOptions:
    trim_whitespaces: bool = False
    remove_comments: bool = False
    keep_newlines: bool = False
    add_end_line_return: bool = True


protocol.implement("jsonc", transformer, JSONCEncoder, lexer="basic")
