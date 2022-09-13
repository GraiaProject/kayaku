from __future__ import annotations

from pydantic import BaseModel
from tomlkit.container import Container


def format_with_model(container: Container, model: type[BaseModel]) -> None:
    ...
