from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from creart import exists_module
from pydantic import Field

from kayaku.model import ConfigModel
from kayaku.provider import AbstractProvider


class _TOMLConfig(ConfigModel, identifier="kayaku.toml_ro", policy="readonly"):
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
    tags = ["file", "toml", "readonly"]
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
