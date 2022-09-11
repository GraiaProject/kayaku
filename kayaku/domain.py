from __future__ import annotations

from typing import ClassVar, Dict, Tuple, Type

from .model import ConfigModel
from .spec import FormattedPath, parse_path, parse_source
from .storage import insert, lookup

DomainType = Tuple[str, ...]

domain_map: dict[DomainType, type[ConfigModel]] = {}


class _Reg:
    _initialized: ClassVar[bool] = False
    """One shot boolean for identifying whether `initialize` is called."""

    _postponed: ClassVar[list[DomainType]] = []


def _insert_domain(domains: DomainType) -> None:
    cls: Type[ConfigModel] = domain_map[domains]
    fmt_path: FormattedPath = lookup(list(domains))
    # TODO: init model and file


def __parse_postponed():
    for domain in _Reg._postponed:
        _insert_domain(domain)
    _Reg._postponed = []
    # initial file checks


def initialize(specs: Dict[str, str], *, __bootstrap: bool = True) -> None:
    exceptions: list[Exception] = []
    for src, path in specs.items():
        try:
            src_spec = parse_source(src)
            path_spec = parse_path(path)
            insert(src_spec, path_spec)
        except Exception as e:
            exceptions.append(e)
    if exceptions:
        raise ValueError(
            f"{len(exceptions)} occurred during initialization.", exceptions
        )
    if __bootstrap:
        __parse_postponed()
        _Reg._initialized = True
