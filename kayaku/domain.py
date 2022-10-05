from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple, Type

from dacite.exceptions import DaciteError

from .backend.types import JObject
from .format import format_with_model
from .schema_gen import ConfigModel, gen_schema_from_list
from .spec import FormattedPath, parse_path, parse_source
from .storage import insert, lookup
from .utils import KayakuEncoder, from_dict

DomainType = Tuple[str, ...]

domain_map: dict[DomainType, type[ConfigModel]] = {}
file_map: dict[Path, dict[DomainType, list[type[ConfigModel]]]] = {}


@dataclass
class _Registry:
    initialized: bool = False

    postponed: list[DomainType] = field(default_factory=list)

    model_path: dict[type[ConfigModel], FormattedPath] = field(default_factory=dict)

    model_map: dict[type[ConfigModel], ConfigModel] = field(default_factory=dict)

    domain_occupation: dict[Path, set[tuple[str, ...]]] = field(default_factory=dict)


_reg = _Registry()


def _insert_domain(domains: DomainType) -> None:
    cls: Type[ConfigModel] = domain_map[domains]
    fmt_path: FormattedPath = lookup(list(domains))
    path = fmt_path.path
    section = tuple(fmt_path.section)
    if section in _reg.domain_occupation.setdefault(path, set()):
        raise NameError(f"{path.as_posix()}::{'.'.join(section)} is occupied!")
    for f_name in cls.__dataclass_fields__:
        sub_sect = section + (f_name,)
        if sub_sect in _reg.domain_occupation[path]:
            raise NameError(f"{path.as_posix()}::{'.'.join(sub_sect)} is occupied!")
        _reg.domain_occupation[path].add(sub_sect)
    file_map.setdefault(path, {}).setdefault(section, []).append(cls)
    _reg.model_path[cls] = fmt_path


def _bootstrap():
    for domain in _reg.postponed:
        _insert_domain(domain)
    _bootstrap_files()
    _reg.initialized = True


def _bootstrap_files():
    from . import backend as json5
    from .pretty import Prettifier

    failed: dict[Path, list[DaciteError]] = {}
    for path, sect_map in file_map.items():
        document = json5.loads(path.read_text(encoding="utf-8") or "{}")
        model_list: list[tuple[DomainType, type[ConfigModel]]] = []
        for sect, classes in sect_map.items():
            model_list.extend((sect, cls) for cls in classes)
            container = document
            for s in sect:
                container = container.setdefault(s, JObject())
            for cls in classes:
                try:
                    _reg.model_map[cls] = from_dict(cls, container)
                except DaciteError as e:
                    failed.setdefault(path, []).append(e)
            for cls in classes:
                format_with_model(container, cls)
        schema_path = path.with_suffix(".schema.json")  # TODO: Customization
        document["$schema"] = schema_path.as_uri()
        with schema_path.open("w", encoding="utf-8") as fp:
            json5.dump(gen_schema_from_list(model_list), fp)
        with path.open("w", encoding="utf-8") as fp:
            json5.dump(Prettifier().prettify(document), fp, KayakuEncoder)
    if failed:
        raise ValueError(failed)


def initialize(specs: Dict[str, str], *, __bootstrap: bool = True) -> None:
    """Initialize Kayaku.

    This operation will load `specs` as a `source pattern -> path pattern` mapping.

    Example:

        class Connection(Dataclass, domain="my_mod.config.connection"):
            account: int | None = None
            "Account"
            password: str | None = None
            "password"

        initialize({"{**}.connection": "./config/connection.jsonc:{**}})

    Above will make `Connection` stored in `./config/connection.jsonc`'s `["my_mod"]["config"]` section.
    """
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
