"""
This modules provides the JSONModule protocol as well as some related helpers.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Literal, Protocol, TextIO, runtime_checkable

from lark.lark import Lark
from lark.visitors import Transformer


@runtime_checkable
class JSONModule(Protocol):
    """
    Protocol for JSON modules implementation.

    Each implementation must be defined as module implementing this protocol.
    """

    transformer: Transformer
    """
    The default transformer instance
    """

    def loads(self, src: str) -> Any:
        """
        Loads data from a string.

        :param src: Some JSON data as string.
        """
        ...

    def load(self, file: TextIO | Path) -> Any:
        """
        Loads data from a file-like object or a Path.

        :param file: A file-like object or path to a file containing JSON to parse.
        """
        ...

    def dumps(self, obj: Any) -> str:
        """
        Serialize data to a string.

        :param obj: The object to serialize as JSON.
        """
        ...

    def dump(self, obj: Any, out: TextIO | Path):
        """
        Serialize data to a file-like object.

        :param obj: The object to serialize as JSON.
        :param out: A file-like object or path to a file to serialize to JSON into.
        """
        ...


class Encoder(Protocol):
    """
    Protocol for JSON encoders
    """

    def encode(self, obj: Any) -> str:
        """
        Serialize any object into a JSON string.

        :param obj: Any supported object to serialize
        :returns: the JSON serialized string representation
        """
        raise NotImplementedError(f"Unknown type: {type(obj)}")


LexerType = Literal["auto", "basic", "contextual", "dynamic", "complete_dynamic"]
"""Lark supported lexer types"""


def implement(
    grammar: str,
    transformer: Transformer,
    encoder: type[Encoder],
    lexer: LexerType = "auto",
):
    """
    A [JSON module][kayaku.backend.protocol.JSONModule] attributes factory.

    Only provide the grammar, the transformer, the encoder class (and a few optional parameters)
    and this factory will create all the missing helpers and boiler plate to implement
    [JSONModule][kayaku.backend.protocol.JSONModule] in the caller module.

    :param grammar: the base name of the grammar (will use the Lark grammar of the same name)
    :param transformer: the instantiated transformer for this grammar
    :param encoder: the default encoder class used on serialization
    :param lexer: optionally specify a lexer implementation for Lark
    """

    parser = Lark.open(
        f"grammar/{grammar}.lark",
        rel_to=__file__,
        lexer=lexer,
        parser="lalr",
        start="value",
        maybe_placeholders=False,
        regex=True,
        # transformer=transformer,
    )

    def loads(src: str) -> Any:
        """
        Parse JSON from a string
        """
        # if DEBUG:
        tree = parser.parse(src)
        return transformer.transform(tree)
        # else:
        #    return parser.parse(src)
        return parser.parse(src)

    def load(file: TextIO | Path) -> str:
        """
        Parse JSON from a file-like object
        """
        data = file.read_text() if isinstance(file, Path) else file.read()
        return loads(data)

    def dumps(obj: Any) -> str:
        """
        Serialize JSON to a string
        """
        return encoder().encode(obj)

    def dump(obj: Any, out: TextIO | Path):
        """
        Serialize JSON to a file-like object
        """
        out = out.open("w") if isinstance(out, Path) else out
        out.write(dumps(obj))
        out.write("\n")

    info = inspect.stack()[1]
    module = inspect.getmodule(info[0])

    if module is None:
        raise RuntimeError(f"Unable to process module from FrameInfo: {info}")

    setattr(module, "parser", parser)
    setattr(module, "loads", loads)
    setattr(module, "load", load)
    setattr(module, "dump", dump)
    setattr(module, "dumps", dumps)
