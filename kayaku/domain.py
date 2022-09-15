from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Dict, Tuple, Type

import pydantic

from .model import ConfigModel
from .spec import FormattedPath, parse_path, parse_source
from .storage import insert, lookup
from .toml_utils.format import format_with_model

DomainType = Tuple[str, ...]

domain_map: dict[DomainType, type[ConfigModel]] = {}
file_map: dict[Path, dict[DomainType, list[type[ConfigModel]]]] = {}
_model_path: dict[type[ConfigModel], FormattedPath] = {}
_model_map: dict[type[ConfigModel], ConfigModel] = {}
_domain_occupation: dict[Path, set[DomainType]] = {}


class _Reg:
    _initialized: ClassVar[bool] = False

    _postponed: ClassVar[list[DomainType]] = []


def _insert_domain(domains: DomainType) -> None:
    cls: Type[ConfigModel] = domain_map[domains]
    fmt_path: FormattedPath = lookup(list(domains))
    path = fmt_path.path
    section = tuple(fmt_path.section)
    if section in _domain_occupation.setdefault(path, set()):
        raise NameError(f"{path.as_posix()}::{'.'.join(section)} is occupied!")
    for f_name in cls.__fields__:
        sub_sect = section + (f_name,)
        if sub_sect in _domain_occupation[path]:
            raise NameError(f"{path.as_posix()}::{'.'.join(sub_sect)} is occupied!")
        _domain_occupation[path].add(sub_sect)
    file_map.setdefault(path, {}).setdefault(section, []).append(cls)
    _model_path[cls] = fmt_path


def _bootstrap():
    for domain in _Reg._postponed:
        _insert_domain(domain)
    _bootstrap_files()
    _Reg._initialized = True


def _bootstrap_files():
    import tomlkit

    for path, sect_map in file_map.items():
        document = tomlkit.loads(path.read_text(encoding="utf-8"))
        failed: list[pydantic.ValidationError] = []
        for sect, classes in sect_map.items():
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
            for cls in classes:
                try:
                    _model_map[cls] = cls.parse_obj(container.unwrap())
                except pydantic.ValidationError as e:
                    failed.append(e)
            for cls in classes:
                format_with_model(container, cls)
        path.write_text(tomlkit.dumps(document), encoding="utf-8")
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
