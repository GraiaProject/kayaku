from typing import Literal

from kayaku.backend.types import Quote
from kayaku.pretty import Prettifier


def prettifier(
    indent: int = 4,
    trail_comma: bool = False,
    key_quote: Quote | None | Literal[False] = Quote.DOUBLE,
    string_quote: Quote | None = Quote.DOUBLE,
    unfold_single: bool = False,
) -> Prettifier:
    return Prettifier(indent, trail_comma, key_quote, string_quote, unfold_single)
