from __future__ import annotations

from typing import ClassVar, Tuple

from .model import ConfigModel

DomainType = Tuple[str, ...]


class DomainRegistry:
    _initialized: ClassVar[bool] = False
    """One shot boolean for identifying whether `initialize` is called."""

    domain_map: ClassVar[dict[DomainType, type[ConfigModel]]] = {}

    _postponed: ClassVar[list[DomainType]] = []


def _insert_domain(domain: DomainType) -> None:
    ...


def __parse_postponed():
    for domain in DomainRegistry._postponed:
        _insert_domain(domain)
    DomainRegistry._postponed = []
