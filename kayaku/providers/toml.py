from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Set

from pydantic import Field

from kayaku.model import ConfigModel
from kayaku.provider import KayakuProvider, RequestTicket
from kayaku.util import exists_module

if TYPE_CHECKING:
    from tomlkit.container import Container


class TOMLConfig(ConfigModel, domain="kayaku.toml", policy="readonly"):
    path: Path
    """The path of the TOML file."""

    encoding: str = "utf-8"
    """The encoding of the TOML file. defaults to UTF-8."""

    root: List[str] = Field(default_factory=list)
    """The root of domain.
    e.g.:
    ```TOML
    [tool.kayaku]
    value_a = 1
    [tool.abc]
    value_b = 2
    ```
    use `domain_root = ["tool"]` to get:
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
    and extracted domain roots are `["kayaku", "abc"]`
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
    use `domain_root=["tool"], filter_keys=["kayaku"]` to get:
    ```json
    {
        "kayaku": {
            "value_a": 1
        }
    }
    ```
    (only include `kayaku`)
    """


class TOMLReadOnlyProvider(KayakuProvider):
    tags = {"toml": 5, "read": 5}
    config_model = TOMLConfig
    data: Dict[str, Any]

    def __init__(self, config: TOMLConfig) -> None:
        self.config: TOMLConfig = config
        self.load()

    @staticmethod
    def available() -> bool:
        return exists_module("tomllib") or exists_module("tomli")

    def load(self) -> None:
        if exists_module("tomllib"):
            import tomllib as tomli  # type: ignore
        else:
            import tomli
        self.data: Dict[str, Any] = tomli.loads(
            self.config.path.read_text(encoding=self.config.encoding)
        )
        for key in self.config.root:
            self.data = self.data.get(key, {})
        if self.config.filter_mode:
            self.data = {
                k: v for k, v in self.data.items() if k in self.config.filter_keys
            }
        else:
            for k in self.config.filter_keys:
                self.data.pop(k)

    async def raw(self, domain: str) -> dict[str, Any]:
        return self.data[domain]

    async def domains(self) -> Set[str]:
        return set(self.data)

    async def fetch(self, model):
        if not model.__domain__:
            raise ValueError(f"{model!r} doesn't have domain!")
        return model.parse_obj(self.data[model.__domain__])

    @KayakuProvider.wrap_request(cache=True)
    def request(self, model, flush: bool = False) -> RequestTicket:
        if not model.__domain__:
            raise ValueError(f"{model!r} doesn't have domain!")
        ticket = RequestTicket(flush)
        if flush:
            self.load()
        ticket.fut.set_result(model.parse_obj(self.data[model.__domain__]))
        return ticket


class TOMLReadWriteProvider(KayakuProvider):
    tags = {"toml": 7, "read": 3, "write": 7}
    config_model = TOMLConfig
    data: Dict[str, Any]

    def __init__(self, config: TOMLConfig) -> None:
        self.config: TOMLConfig = config
        self.load()

    @staticmethod
    def available() -> bool:
        return exists_module("tomlkit")

    def load_container(self, container: Container) -> None:
        data = container.copy()
        for key in self.config.root:
            data = data.get(key, {})
        if self.config.filter_mode:
            data = {k: v for k, v in self.data.items() if k in self.config.filter_keys}
        else:
            for k in self.config.filter_keys:
                data.pop(k)
        self.data = data

    def load(self) -> None:
        import tomlkit.api
        import tomlkit.toml_document

        self.document: tomlkit.toml_document.TOMLDocument = tomlkit.api.loads(
            self.config.path.read_text(encoding=self.config.encoding)
        )
        self.load_container(self.document)

    async def raw(self, domain: str) -> dict[str, Any]:
        return self.data[domain]

    @KayakuProvider.wrap_request(cache=True)
    def request(self, model, flush: bool = False) -> RequestTicket:
        if not model.__domain__:
            raise ValueError(f"{model!r} doesn't have domain!")
        ticket = RequestTicket(flush)
        if flush:
            self.load()
        ticket.fut.set_result(model.parse_obj(self.data[model.__domain__]))
        return ticket

    async def domains(self) -> Set[str]:
        return set(self.data)

    async def fetch(self, model):
        if not model.__domain__:
            raise ValueError(f"{model!r} doesn't have domain!")
        return model.parse_obj(self.data[model.__domain__])

    async def write(self, domain: str, data: Dict[str, Any]) -> None:
        import tomlkit.api
        from tomlkit.container import Container

        container = self.document
        for key in self.config.root:
            container = container.get(key, Container())
        container = container.setdefault(domain, Container())
        container.update(data)
        self.config.path.write_text(
            tomlkit.api.dumps(self.document), encoding=self.config.encoding
        )
        self.load_container(self.document)
