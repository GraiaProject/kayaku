from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Set

from pydantic import Field

from kayaku.model import ConfigModel
from kayaku.provider import AbstractProvider
from kayaku.util import exists_module

if TYPE_CHECKING:
    from tomlkit.container import Container


class _TOMLConfig(ConfigModel, identifier="kayaku.toml", policy="readonly"):
    path: Path
    """The path of the TOML file."""

    encoding: str = "utf-8"
    """The encoding of the TOML file. defaults to UTF-8."""

    identifier_root: List[str] = Field(default_factory=list)
    """The root of identifier namespace.
    e.g.:
    ```TOML
    [tool.kayaku]
    value_a = 1
    [tool.abc]
    value_b = 2
    ```
    use `identifier_root = ["tool"]` to get:
    ```json
    {
        "kayaku": {
            "value_a": 1
        },
        "abc": {
            "value_b": 2
        }
    }
    ```
    and extracted identifier roots are `["kayaku", "abc"]`
    """
    filter_mode: bool = False
    """Filter mode.
    indicating `include (true)` `exclude (false)`
    """
    filter_keys: Set[str] = Field(default_factory=lambda: set())
    """The filter keys, which is a list of string indicating the keys.
    e.g.:
    ```TOML
    [tool.kayaku]
    value_a = 1
    [tool.abc]
    value_b = 2
    ```
    use `identifier_root=["tool"], filter_keys=["kayaku"]` to get:
    ```json
    {
        "kayaku": {
            "value_a": 1
        }
    }
    ```
    (only include `kayaku`)
    """


class TOMLReadOnlyProvider(AbstractProvider):
    tags = ["file", "toml", "read", "readonly"]
    config_cls = _TOMLConfig
    data: Dict[str, Any]

    def __init__(self, config: _TOMLConfig) -> None:
        self.config: _TOMLConfig = config

    @staticmethod
    def available() -> bool:
        return exists_module("tomllib") or exists_module("tomli")

    async def load(self) -> None:
        if exists_module("tomllib"):
            import tomllib as tomli  # type: ignore
        else:
            import tomli
        self.data: Dict[str, Any] = tomli.loads(
            self.config.path.read_text(encoding=self.config.encoding)
        )
        for key in self.config.identifier_root:
            self.data = self.data.get(key, {})
        if self.config.filter_mode:
            self.data = {
                k: v for k, v in self.data.items() if k in self.config.filter_keys
            }
        else:
            for k in self.config.filter_keys:
                self.data.pop(k)

    async def provided_identifiers(self) -> Set[str]:
        return set(self.data)

    async def fetch(self, model):
        if not model.__identifier__:
            raise ValueError(f"{model!r} doesn't have identifier!")
        return model.parse_obj(self.data[model.__identifier__])


class TOMLReadWriteProvider(AbstractProvider):
    tags = ["file", "toml", "read", "write"]
    config_cls = _TOMLConfig
    data: Dict[str, Any]

    def __init__(self, config: _TOMLConfig) -> None:
        self.config: _TOMLConfig = config

    @staticmethod
    def available() -> bool:
        return exists_module("tomlkit")

    def load_container(self, container: Container) -> None:
        data = container.copy()
        for key in self.config.identifier_root:
            data = data.get(key, {})
        if self.config.filter_mode:
            data = {k: v for k, v in self.data.items() if k in self.config.filter_keys}
        else:
            for k in self.config.filter_keys:
                data.pop(k)
        self.data = data

    async def load(self) -> None:
        import tomlkit.api
        import tomlkit.toml_document

        self.document: tomlkit.toml_document.TOMLDocument = tomlkit.api.loads(
            self.config.path.read_text(encoding=self.config.encoding)
        )
        self.load_container(self.document)

    async def provided_identifiers(self) -> Set[str]:
        return set(self.data)

    async def fetch(self, model):
        if not model.__identifier__:
            raise ValueError(f"{model!r} doesn't have identifier!")
        return model.parse_obj(self.data[model.__identifier__])

    async def apply(self, identifier: str, data: Dict[str, Any]) -> None:
        import tomlkit.api
        from tomlkit.container import Container

        container = self.document
        for key in self.config.identifier_root:
            container = container.get(key, Container())
        container = container.setdefault(identifier, Container())
        container.update(data)
        self.config.path.write_text(
            tomlkit.api.dumps(self.document), encoding=self.config.encoding
        )
        self.load_container(self.document)
