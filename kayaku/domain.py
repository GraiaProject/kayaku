from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import fields as get_fields
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Type

from .backend import dumps, loads
from .backend.types import JObject
from .format import format_with_model
from .pretty import Prettifier
from .schema_gen import ConfigModel, SchemaGenerator, write_schema_ref
from .spec import FormattedPath, parse_path, parse_source
from .storage import insert, lookup
from .utils import from_dict, update

MountType = Tuple[str, ...]
DomainType = Tuple[str, ...]


@dataclass
class _FileStore:
    generator: SchemaGenerator
    schemas: dict = field(default_factory=dict)
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
    prettifier: Prettifier
    generator_cls: Type[SchemaGenerator]
    files: Dict[Path, _FileStore] = field(default_factory=dict)
    models: Dict[DomainType, _ModelStore] = field(default_factory=dict)
    cls_domains: Dict[Type[ConfigModel], DomainType] = field(default_factory=dict)


_store: _GlobalStore


def insert_domain(domain: DomainType, cls: Type[ConfigModel]) -> None:
    _store.cls_domains[cls] = domain
    fmt_path: FormattedPath = lookup(list(domain))
    path = fmt_path.path
    mount_dest = tuple(fmt_path.mount_dest)
    file_store = _store.files.setdefault(path, _FileStore(_store.generator_cls(None)))
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


def initialize(
    specs: Dict[str, str],
    prettifier: Optional[Prettifier] = None,
    schema_generator_cls: Type[SchemaGenerator] = SchemaGenerator,
) -> None:
    """初始化 Kayaku.

    本函数需要最先被调用.

    Args:
        specs (Dict[str, str]): `domain 样式 -> 路径样式` 的映射.
        prettifier (Prettifier, optional): 格式化器.
        schema_generator_cls (Type[SchemaGenerator], optional): JSON Schema 生成器的类.

    Example:

        ```py
        from kayaku import bootstrap, config, initialize

        initialize({"{**}.connection": "./config/connection.jsonc::{**}})

        @config("my_mod.config.connection")
        class Connection:
            account: int | None = None
            "Account"
            password: str | None = None
            "password"

        bootstrap()
        ```

        以上代码将会将 `Connection` 类的数据存储在 `./config/connection.jsonc` 文件的 `["my_mod"]["config"]` 里.
    """
    global _store
    _store = _GlobalStore(prettifier or Prettifier(), schema_generator_cls)
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
    """预处理所有 `ConfigModel` 并写入默认值和 JSON Schema.

    建议在加载完外部模块后调用.
    """

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
                format_with_model(container, model_store.cls)
        document.pop("$schema", None)
        document["$schema"] = path.with_suffix(".schema.json").as_uri()
        path.write_text(
            dumps(_store.prettifier.prettify(document), endline=True), "utf-8"
        )
    if exceptions:
        raise ValueError(exceptions)


def save_all() -> None:
    """保存所有容器，并格式化。

    可以在退出前调用本函数。
    """

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
            dumps(_store.prettifier.prettify(document), endline=True), "utf-8"
        )
