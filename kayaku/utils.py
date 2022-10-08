from __future__ import annotations

import enum
import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from typing import Any, TextIO, TypeVar

from dacite.config import Config
from dacite.core import from_dict as _from_dict
from typing_extensions import TypeAlias

from .backend import Encoder
from .backend.types import Array, JObject, convert
from .schema_gen import ConfigModel

DomainType: TypeAlias = "tuple[str, ...]"

T = TypeVar("T", bound=ConfigModel)


def update(container: dict, data: Any, delete: bool = False):
    if container == data:
        return
    assert isinstance(container, dict)
    container = convert(container)
    assert isinstance(data, Mapping)
    for k, v in data.items():
        if (
            k in container
            and isinstance(v, Mapping)
            and isinstance(container[k], v.__class__)
        ):
            update(container[k], v)
        else:
            container[k] = v
    if delete:
        for k in [k for k in container if k not in data]:
            del container[k]


def from_dict(model: type[T], data: dict[str, Any]) -> T:
    return _from_dict(
        model,
        data,
        Config(
            type_hooks={
                datetime: datetime.fromisoformat,
                time: time.fromisoformat,
                date: date.fromisoformat,
                re.Pattern: re.compile,
            },
            cast=[enum.Enum],
        ),
    )


class KayakuEncoder(Encoder):
    def __init__(self, fp: TextIO):
        super().__init__(fp)
        self.encode_func.update(
            {
                (datetime, date, time): self.encode_datetime,
                (re.Pattern,): self.encode_re_pattern,
                (enum.Enum,): self.encode_enum,
            }
        )

    def encode_enum(self, obj: enum.Enum) -> None:
        return self.encode(obj.value)

    def encode_datetime(self, obj: datetime | date | time) -> None:
        return self.encode_string(obj.isoformat())

    def encode_re_pattern(self, obj: re.Pattern) -> None:
        return self.encode_string(obj.pattern)
