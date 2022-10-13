from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import fields as get_fields
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Type

from kayaku.backend.types import JObject

from .format import format_with_model
from .schema_gen import ConfigModel, Schema, SchemaGenerator, write_schema_ref
from .spec import FormattedPath, parse_path, parse_source
from .storage import insert, lookup
from .utils import update

MountType = Tuple[str, ...]
DomainType = Tuple[str, ...]


@dataclass
class _FileStore:
    schemas: dict = field(default_factory=dict)
    generator: SchemaGenerator = field(default_factory=lambda: SchemaGenerator(None))
    mount: Dict[MountType, List[DomainType]] = field(default_factory=dict)
    field_mount_record: Set[MountType] = field(default_factory=set)

    def get_schema(self) -> dict:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **self.schemas,
            "$defs": self.generator.defs,
        }


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
        sub_dest: MountType = mount_dest + (field.name,)
        if sub_dest in file_store.field_mount_record:
            raise NameError(f"{path.as_posix()}::{'.'.join(sub_dest)} is occupied!")
        file_store.field_mount_record.add(sub_dest)
    file_store.mount.setdefault(mount_dest, []).append(domain)
    _store.models[domain] = _ModelStore(cls, fmt_path, None)
    file_store.generator.get_dc_schema(cls)
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
    from .backend import dumps, loads
    from .utils import from_dict

    exceptions = []

    for path, store in _store.files.items():
        document = loads(path.read_text("utf-8") or "{}")
        path.with_suffix(".schema.json").write_text(
            dumps(store.get_schema()), encoding="utf-8"
        )
        for mount_dest, domains in store.mount.items():
            container = document
            for sect in mount_dest:
                container = container.setdefault(sect, JObject())
            for domain in domains:
                model_store = _store.models[domain]
                if model_store.instance is None:
                    try:
                        model_store.instance = from_dict(model_store.cls, container)
                    except Exception as e:
                        exceptions.append((path, mount_dest, model_store.cls, e))
    if exceptions:
        raise ValueError(exceptions)


def save_all() -> None:
    """Save every model in kayaku and format containers.

    Please call this function on cleanup.
    """
    from .backend import dumps, loads
    from .pretty import Prettifier

    for path, store in _store.files.items():
        document = loads(path.read_text("utf-8") or "{}")
        path.with_suffix(".schema.json").write_text(
            dumps(store.get_schema()), encoding="utf-8"
        )
        for mount_dest, domains in store.mount.items():
            container = document
            for sect in mount_dest:
                container = container.setdefault(sect, JObject())
            for domain in domains:
                model_store = _store.models[domain]
                if model_store.instance is not None:
                    update(container, model_store.instance)
                format_with_model(container, model_store.cls)
            document.pop("$schema", None)
            document["$schema"] = path.with_suffix(".schema.json").as_uri()
            path.write_text(
                dumps(Prettifier().prettify(document), endline=True), "utf-8"
            )
