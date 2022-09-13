from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Dict, Tuple, Type

import pydantic

from .formatter import format_with_model
from .model import ConfigModel
from .spec import FormattedPath, parse_path, parse_source
from .storage import insert, lookup

DomainType = Tuple[str, ...]

domain_map: dict[DomainType, type[ConfigModel]] = {}

file_map: dict[Path, dict[DomainType, type[ConfigModel]]] = {}

_model_map: dict[type[ConfigModel], ConfigModel] = {}


class _Reg:
    _initialized: ClassVar[bool] = False

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
    _bootstrap_files()
    _Reg._initialized = True


def _bootstrap_files():
    import tomlkit

    for path, sect_map in file_map.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        document = tomlkit.loads(path.read_text(encoding="utf-8"))
        failed: list[pydantic.ValidationError] = []
        for sect, cls in sect_map.items():
            try:
                container: Any = document
                for s in sect:
                    container = container[s]
            except KeyError:
                tables = [tomlkit.table(True) for _ in sect[:-1]] + [tomlkit.table()]
                for i in reversed(range(1, len(sect))):
                    tables[i - 1].append(sect[i], tables[i])
                document.append(sect[0], tables[0])
                container = tables[-1]
            try:
                _model_map[cls] = cls.parse_obj(container)
            except pydantic.ValidationError as e:
                failed.append(e)
            format_with_model(container, cls)
        print(tomlkit.dumps(document))
        if failed:
            raise ValueError(f"{len(failed)} models failed to validate.", failed)


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
