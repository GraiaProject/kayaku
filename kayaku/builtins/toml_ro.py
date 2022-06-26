try:
    import tomllib  # type: ignore
except ImportError:
    import tomli as tomllib

from pathlib import Path
from typing import ClassVar

from kayaku.provider import BaseProvider


class TomlReadOnlyProvider(BaseProvider):
    identity: ClassVar[str] = "toml"
    ...
