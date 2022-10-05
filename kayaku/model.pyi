from __future__ import annotations

from collections.abc import Callable
from dataclasses import Field, field
from typing import TypeVar

from typing_extensions import dataclass_transform

from .schema_gen import ConfigModel

@dataclass_transform(field_specifiers=(Field, field))
def config(
    *,
    domain: str,
    init=True,
    repr=True,
    eq=True,
    order=False,
    unsafe_hash=False,
    frozen=False,
    match_args=True,
    kw_only=False,
    slots=False,
) -> Callable[[type], type[ConfigModel]]: ...

T = TypeVar("T")

def create(cls: type[T], flush: bool = False) -> T:
    """Create a model.

    Specifying `flush` will force a model-level data reload.

    Note: It's *highly* recommended that you `create` a model every time (for safe reload).
    """
    ...

def save(model: T | type[T]) -> None:
    """Save a model."""
    ...

def save_all() -> None:
    """Save every model in kayaku.

    Very useful if you want to reflect changes on cleanup.
    """
    ...
