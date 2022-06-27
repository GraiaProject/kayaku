from pathlib import Path
from typing import Any, Dict, Set

import tomli

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
        self.data: Dict[str, Any] = tomli.loads(
            config.path.read_text(encoding=config.encoding)
        )

    async def provided_identities(self) -> Set[str]:
        return set(self.data)

    async def fetch(self, model):
        if not model.__identity__:
            raise ValueError(f"{model!r} doesn't have identity!")
        return model.parse_obj(self.data[model.__identity__])
