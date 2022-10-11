from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import fields as get_fields
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Type

from .schema_gen import ConfigModel, SchemaAnnotation, SchemaGenerator, write_schema_ref
from .spec import FormattedPath, parse_path, parse_source
from .storage import insert, lookup

MountType = Tuple[str, ...]
DomainType = Tuple[str, ...]

domain_map: dict[DomainType, type[ConfigModel]] = {}
file_map: dict[Path, dict[DomainType, list[type[ConfigModel]]]] = {}


@dataclass
class _FileStore:
    schemas: dict = field(
        default_factory=lambda: {
            "$schema": "https://json-schema.org/draft/2020-12/schema"
        }
    )
    generator: SchemaGenerator = field(default_factory=lambda: SchemaGenerator(None))
    mount: Dict[MountType, List[DomainType]] = field(default_factory=dict)
    field_mount_record: Set[MountType] = field(default_factory=set)


@dataclass
class _ModelStore:
    cls: Type[ConfigModel]
    location: FormattedPath
    instance: Optional[ConfigModel]


@dataclass
class _GlobalStore:
    files: Dict[Path, _FileStore] = field(default_factory=dict)
    models: Dict[DomainType, _ModelStore] = field(default_factory=dict)
    cls_domains: Dict[Type[ConfigModel], DomainType] = field(default_factory=dict)


_store = _GlobalStore()


def insert_domain(domain: DomainType, cls: Type[ConfigModel]) -> None:
    _store.cls_domains[cls] = domain
    fmt_path: FormattedPath = lookup(list(domain))
    path = fmt_path.path
    mount_dest = tuple(fmt_path.mount_dest)
    file_store = _store.files.setdefault(path, _FileStore())
    for field in get_fields(cls):
        sub_dest = mount_dest + (field.name,)
        if sub_dest in file_store.field_mount_record:
            raise NameError(f"{path.as_posix()}::{'.'.join(mount_dest)} is occupied!")
        file_store.field_mount_record.add(sub_dest)
    _store.models[domain] = _ModelStore(cls, fmt_path, None)
    file_store.generator.get_dc_schema(cls, SchemaAnnotation())
    write_schema_ref(
        file_store.schemas, mount_dest, file_store.generator.retrieve_name(cls)
    )


def initialize(specs: Dict[str, str]) -> None:
    """Initialize Kayaku.

    This operation will load `specs` as a `source pattern -> path pattern` mapping.

    Example:

        class Connection(Dataclass, domain="my_mod.config.connection"):
            account: int | None = None
            "Account"
            password: str | None = None
            "password"

        initialize({"{**}.connection": "./config/connection.jsonc::{**}})

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
            f"{len(exceptions)} occurred during spec initialization.", exceptions
        )


def bootstrap() -> None:
    """Populates json schema and default data for all `ConfigModel` that have registered."""
