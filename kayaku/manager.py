from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from dataclasses import fields as get_fields
from pathlib import Path
from typing import Any, Literal, TypeAlias, TypeVar, overload

from .backend import dumps, loads
from .backend.types import JObject, Quote
from .bi_tree import Prefix
from .format import format_with_model
from .pretty import Prettifier
from .schema_gen import DataClass, SchemaGenerator, update_schema_ref
from .spec import DestWithMount, PathSpec, SourceSpec, parse_path, parse_source
from .utils import from_dict, to_path, touch_path, update

SchemaGenCallable: TypeAlias = Callable[[type[DataClass] | None], SchemaGenerator]
StrStrip: TypeAlias = tuple[str, ...]

MountIdent: TypeAlias = StrStrip
DomainIdent: TypeAlias = StrStrip


@dataclass
class _FileEntry:
    generator: SchemaGenerator
    schemas: dict = field(default_factory=dict)
    mount: dict[MountIdent, list[DomainIdent]] = field(default_factory=dict)
    mount_record: set[DomainIdent] = field(default_factory=set)

    def get_schema(self) -> dict:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **self.schemas,
            "$defs": self.generator.defs,
        }


@dataclass
class _ClassEntry:
    cls: type[DataClass]
    path: Path
    mount: MountIdent


@dataclass
class _KayakuCore:
    file_suffix: str
    prettifier: Prettifier
    get_schema_generator: SchemaGenCallable

    def __post_init__(self):
        self.files: dict[Path, _FileEntry] = dict()
        self.classes: dict[DomainIdent, _ClassEntry] = dict()
        self.cls_domains: dict[type[DataClass], DomainIdent] = dict()
        self.instances: dict[type[DataClass], DataClass] = dict()
        self.root = Prefix()

    def insert_spec(self, src: SourceSpec, path: PathSpec) -> None:
        prefix, suffix = src.prefix, src.suffix
        target_nd = self.root.insert(prefix).insert(reversed(suffix))
        if target_nd.bound:
            raise ValueError(
                f"{'.'.join(prefix + ['*'] + suffix)} is already bound to {target_nd.bound}"
            )
        target_nd.bound = (src, path)

    def lookup_path(self, domains: Sequence[str]) -> DestWithMount:
        if res := self.root.lookup(domains):
            return res[1]
        raise ValueError(f"Unable to lookup {'.'.join(domains)}")

    def register(self, domain: DomainIdent, cls: type[DataClass]) -> Path:
        self.cls_domains[cls] = domain
        path_info: DestWithMount = self.lookup_path(domain)
        path = to_path(path_info.dest, "." + self.file_suffix)
        mount = path_info.mount
        file_store = self.files.setdefault(
            path, _FileEntry(self.get_schema_generator(None))
        )
        for dc_field in get_fields(cls):
            sub_dest: MountIdent = mount + (dc_field.name,)
            if sub_dest in file_store.mount_record:
                raise NameError(
                    f"{path.with_suffix('').as_posix()}::{'.'.join(sub_dest)} is occupied!"
                )
            file_store.mount_record.add(sub_dest)
        file_store.mount.setdefault(mount, []).append(domain)
        self.classes[domain] = _ClassEntry(cls, path, mount)
        file_store.generator.get_dc_schema(cls)
        update_schema_ref(
            file_store.schemas, mount, file_store.generator.retrieve_name(cls)
        )
        return path

    def register_batch(self, domain_map: dict[str, type[DataClass]]) -> None:
        exceptions = []
        paths = set()
        for domain, cls in domain_map.items():
            domain_ident = tuple(domain.split("."))
            try:
                if not all(domain_ident):
                    raise ValueError(f"{domain!r} contains empty segment!")
                elif domain_ident in self.classes:
                    raise NameError(
                        f"{domain!r} is already occupied by {self.classes[domain_ident].cls!r}"
                    )
                path = self.register(domain_ident, cls)
                paths.add(path)
            except Exception as e:
                exceptions.append(e)
        if exceptions:
            raise ExceptionGroup(
                f"{len(exceptions)} occurred during class registration", exceptions
            )
        self.bootstrap(paths)

    def bootstrap_file(self, path: Path, store: _FileEntry) -> None:
        path.with_suffix(".schema.json").write_text(
            dumps(store.get_schema()), encoding="utf-8"
        )
        exceptions = []
        if path.exists() and (text := path.read_text(encoding="utf-8")):
            document = loads(text)
        else:
            touch_path(path)
            document = loads("{}")
        for mount, domains in store.mount.items():
            container = document
            for sect in mount:
                container = container.setdefault(sect, JObject())
            for domain in domains:
                cls_entry = self.classes[domain]
                if self.instances.get(cls_entry.cls) is None:
                    try:
                        self.instances[cls_entry.cls] = from_dict(
                            cls_entry.cls, container
                        )
                    except Exception as e:
                        exceptions.append(
                            ExceptionGroup(
                                f"Failed to bootstrap {cls_entry.cls} at {'.'.join(mount)}",
                                [e],
                            )
                        )
                format_with_model(container, cls_entry.cls)
        document.pop("$schema", None)
        document["$schema"] = path.with_suffix(".schema.json").as_uri()
        path.write_text(
            dumps(self.prettifier.prettify(document), endline=True), "utf-8"
        )
        if exceptions:
            raise ExceptionGroup(
                f"{len(exceptions)} errors occurred bootstrapping {path}", exceptions
            )

    def bootstrap(self, paths: set[Path]) -> None:
        exception_groups = []
        for path in paths:
            try:
                self.bootstrap_file(path, self.files[path])
            except ExceptionGroup as e:
                exception_groups.append(e)
            except Exception as e:
                exception_groups.append(
                    ExceptionGroup(f"Error occurred during {path}", [e])
                )
        if exception_groups:
            raise ExceptionGroup(
                f"{len(exception_groups)} files failed to bootstrap", exception_groups
            )


FileSetup = str | tuple[str, Prettifier]

JSONC_PRETTIFIER = Prettifier(
    trail_comma=False, key_quote=Quote.DOUBLE, string_quote=Quote.DOUBLE
)
JSON5_PRETTIFIER = Prettifier(
    trail_comma=True, key_quote=False, string_quote=Quote.DOUBLE
)

DC_T = TypeVar("DC_T", bound=DataClass)


class Kayaku:
    """配置管理器。

    Example:

        ```py
        from dataclasses import dataclass

        from kayaku import ConfigManager

        cfg_manager = ConfigManager({"{**}.connection": "./config/connection.jsonc::{**}})

        @dataclass
        class Connection:
            account: int | None = None
            password: str | None = None

        cfg_manager.register("my_mod.config.connection", Connection)
        cfg_manager.load()
        ```

        以上代码将会将 `Connection` 类的数据存储在 `./config/connection.jsonc` 文件的 `["my_mod"]["config"]` 里.
    """

    """`domain 样式 -> 路径样式` 的映射。"""
    """美化 JSONC/JSON5 文件时使用。默认根据文件后缀自动选择。"""
    """在获取 JSON Schema 时使用的生成器。"""

    def __init__(
        self,
        specs: dict[str, str],
        file_suffix: str = "json5",
        prettifier: Prettifier | None = None,
        get_schema_generator: SchemaGenCallable = SchemaGenerator,
    ) -> None:
        self.file_suffix = file_suffix
        self.get_schema_generator = get_schema_generator
        if prettifier:
            self.prettifier = prettifier
        else:
            self.prettifier: Prettifier = (
                JSON5_PRETTIFIER if self.file_suffix != "jsonc" else JSONC_PRETTIFIER
            )
        self._core = _KayakuCore(
            self.file_suffix, self.prettifier, self.get_schema_generator
        )
        exceptions = []
        for src, path in specs.items():
            try:
                src_spec = parse_source(src)
                path_spec = parse_path(path)
                self._core.insert_spec(src_spec, path_spec)
            except Exception as e:
                exceptions.append(e)
        if exceptions:
            raise ExceptionGroup(
                f"{len(exceptions)} occurred during spec initialization", exceptions
            )

    def load(self, domain_map: dict[str, type[DataClass]]) -> None:
        """加载配置类。"""
        self._core.register_batch(domain_map)

    @overload
    def get(self, cls: type[DC_T], safe: Literal[False] = False) -> DC_T: ...

    @overload
    def get(self, cls: type[DC_T], safe: Literal[True]) -> DC_T | None: ...

    def get(self, cls: type[DC_T], safe: bool = False) -> DC_T | None:
        """获取配置类的实例。"""
        res: Any = self._core.instances.get(cls)
        if res is None and not safe:
            raise ValueError(f"{cls} is not loaded!")
        return res

    def save(self, config: type[DataClass] | DataClass | DomainIdent) -> None:
        if isinstance(config, type):
            domain = self._core.cls_domains[config]
        elif isinstance(config, DataClass):
            domain = self._core.cls_domains[config.__class__]
        else:
            domain = config
        cls_entry = self._core.classes[domain]
        instance = (
            config
            if isinstance(config, DataClass) and not isinstance(config, type)
            else self.get(cls_entry.cls, safe=True)
        )
        if not instance:
            raise ValueError(f"{cls_entry.cls} is not loaded!")
        document = loads(cls_entry.path.read_text("utf-8") or "{}")
        container = document
        for sect in cls_entry.mount:
            container = container.setdefault(sect, JObject())
        update(container, instance)
        document.pop("$schema", None)
        document["$schema"] = cls_entry.path.with_suffix(".schema.json").as_uri()
        cls_entry.path.write_text(
            dumps(self._core.prettifier.prettify(document), endline=True), "utf-8"
        )
        cls_entry.path.with_suffix(".schema.json").write_text(
            dumps(self._core.files[cls_entry.path].get_schema()), "utf-8"
        )
