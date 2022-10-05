from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from typing import Any, TextIO, TypeVar

from dacite.config import Config
from dacite.core import from_dict as _from_dict
from typing_extensions import TypeAlias

from .backend import Encoder
from .backend.types import Array, JObject
from .schema_gen import ConfigModel

DomainType: TypeAlias = "tuple[str, ...]"

T = TypeVar("T", bound=ConfigModel)


def update(container: JObject | Array, data: Any, delete: bool = False):
    if container == data:
        return
    if isinstance(container, JObject):
        assert isinstance(data, Mapping)
        for k, v in data.items():
            if (
                k in container
                and isinstance(v, (Mapping, Sequence))
                and isinstance(container[k], v.__class__)
            ):
                update(container[k], v)
            else:
                container[k] = v
        if delete:
            for k in [k for k in container if k not in data]:
                del container[k]
    else:
        assert isinstance(data, Sequence)
        if len(data) > len(container):
            container.extend(None for _ in range(len(data) - len(container)))
        else:
            while len(container) > len(data):
                print(container)
                container.pop()
        for (i, v) in enumerate(data):
            if container[i] != v:
                container[i] = v


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
            }
        ),
    )


class KayakuEncoder(Encoder):
    def __init__(self, fp: TextIO):
        super().__init__(fp)
        self.encode_func.update(
            {
                (datetime, date, time): self.encode_datetime,
                (re.Pattern,): self.encode_re_pattern,
            }
        )

    def encode_datetime(self, obj: datetime | date | time):
        return self.encode_string(obj.isoformat())

    def encode_re_pattern(self, obj: re.Pattern) -> None:
        return self.encode_string(obj.pattern)
