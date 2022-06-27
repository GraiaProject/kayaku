try:
    import tomllib  # type: ignore
except ImportError:
    import tomli as tomllib

from pathlib import Path
from typing import ClassVar

from kayaku.provider import AbstractProvider


class TomlReadOnlyProvider(AbstractProvider):
    tags = ["file", "toml", "readonly"]
    ...
