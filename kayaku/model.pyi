from collections.abc import Callable
from dataclasses import Field

from typing_extensions import dataclass_transform

class ConfigModel:
    __dataclass_fields__: dict[str, Field]

@dataclass_transform()
def config(
    cls=None,
    /,
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
) -> Callable[[type], type[ConfigModel]] | type[ConfigModel]: ...
