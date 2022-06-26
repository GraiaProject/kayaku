try:
    import tomllib  # type: ignore
except ImportError:
    import tomli as tomllib

from pathlib import Path

from kayaku.provider import BaseProvider


class TomlReadOnlyProvider(BaseProvider):
    # TODO
    ...
