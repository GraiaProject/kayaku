"""
This module handles whitespaces and comments
"""

from __future__ import annotations

from lark.lark import Lark
from lark.lexer import Token
from lark.visitors import Transformer, v_args

from .types import WSC, BlockStyleComment, LineStyleComment, WhiteSpace


class WSCTransformer(Transformer):
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

    def wscs(self, wscs: list[WSC]) -> list[WSC]:
        return wscs


transformer = WSCTransformer()


def encode_wsc(wsc: WSC):
    """
    Encode a [WSC][kayaku.backend.types.WSC] into its string representation.

    :param wsc: The Whitespace or Comment to encode.
    """
    if isinstance(wsc, LineStyleComment):
        return f"//{wsc}"
    if isinstance(wsc, BlockStyleComment):
        return f"/*{wsc}*/"
    if isinstance(wsc, WhiteSpace):
        return str(wsc)
    raise NotImplementedError(f"Unknown whitespace or comment type: {wsc!r}")


parser = Lark.open(
    "grammar/wsc.lark",
    rel_to=__file__,
    lexer="basic",
    parser="lalr",
    start="wscs",
    maybe_placeholders=False,
    regex=True,
    transformer=transformer,
)
