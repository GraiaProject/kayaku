from pathlib import Path
from typing import Any, Dict, Set

from creart import exists_module

from kayaku.model import ConfigModel
from kayaku.provider import AbstractProvider


class TOMLReadOnlyProviderConfig(
    ConfigModel, identity="toml_ro_config", policy="readonly"
):
    path: Path
    encoding: str = "utf-8"


class TOMLReadOnlyProvider(AbstractProvider):
    tags = ["file", "toml", "readonly"]
    config = TOMLReadOnlyProviderConfig

    def __init__(self, config: TOMLReadOnlyProviderConfig) -> None:
        if exists_module("tomllib"):
            import tomllib as tomli  # type: ignore
        else:
            import tomli
        self.data: Dict[str, Any] = tomli.loads(
            config.path.read_text(encoding=config.encoding)
        )

    @staticmethod
    def available() -> bool:
        return exists_module("tomllib") or exists_module("tomli")

    async def provided_identities(self) -> Set[str]:
        return set(self.data)

    async def fetch(self, model):
        if not model.__identity__:
            raise ValueError(f"{model!r} doesn't have identity!")
        return model.parse_obj(self.data[model.__identity__])
