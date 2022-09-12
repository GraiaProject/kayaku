from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Dict, Tuple, Type

from .model import ConfigModel
from .spec import FormattedPath, parse_path, parse_source
from .storage import insert, lookup

DomainType = Tuple[str, ...]

domain_map: dict[DomainType, type[ConfigModel]] = {}

file_map: dict[Path, dict[DomainType, type[ConfigModel]]] = {}


class _Reg:
    _initialized: ClassVar[bool] = False
    """One shot boolean for identifying whether `initialize` is called."""

    _postponed: ClassVar[list[DomainType]] = []


def _insert_domain(domains: DomainType) -> None:
    cls: Type[ConfigModel] = domain_map[domains]
    fmt_path: FormattedPath = lookup(list(domains))
    path = fmt_path.path.with_suffix(".toml")  # TODO: hocon
    section = tuple(fmt_path.section)
    file_map.setdefault(path, {}).setdefault(section, cls)


def _bootstrap():
    for domain in _Reg._postponed:
        _insert_domain(domain)
    _Reg._initialized = True


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
        _bootstrap()
