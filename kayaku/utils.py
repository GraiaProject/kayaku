from __future__ import annotations

import enum
import re
from dataclasses import fields
from datetime import date, datetime, time
from typing import Any, TypeVar, Union

import typing_extensions
from dacite.config import Config
from dacite.core import from_dict as _from_dict
from typing_extensions import TypeAlias

from .backend.types import JContainer, JObject, JType, JWrapper, convert
from .schema_gen import ConfigModel

DomainType: TypeAlias = "tuple[str, ...]"

T = TypeVar("T", bound=ConfigModel)


def copy_meta(src: Any, dst: JType):
    if isinstance(dst, JContainer):
        dst.json_container_trailing_comma = getattr(
            src, "json_container_trailing_comma", False
        )
        dst.json_container_tail = getattr(src, "json_container_tail", [])
    dst.json_before = getattr(src, "json_before", [])
    dst.json_after = getattr(src, "json_after", [])


def update(container: dict[str, Any], data: ConfigModel | dict, delete: bool = False):
    container = convert(container)
    if isinstance(data, ConfigModel):
        k_v_pairs = {f.name: getattr(data, f.name) for f in fields(data)}
    else:
        k_v_pairs = data
    to_be_popped: set[str] = set(container.keys() if delete else ())
    for k, v in k_v_pairs.items():
        to_be_popped.discard(k)
        origin_v = container.get(k, None)
        if isinstance(v, (ConfigModel, dict)):
            if origin_v is not None and not isinstance(origin_v, dict):
                container[k] = new_v = JObject()
                copy_meta(origin_v, new_v)
            update(container.setdefault(k, {}), v, delete=True)
            continue
        if isinstance(v, (re.Pattern, date, datetime, time)):
            v = convert(v.pattern if isinstance(v, re.Pattern) else v.isoformat())
        else:
            v = convert(v)
        if origin_v is not None:
            copy_meta(origin_v, v)
        container[k] = v
    for k in to_be_popped:
        container.pop(k, Any)
    # TODO: Sequence


class _KayakuDaciteTypeHook(dict):
    def __init__(self):
        super().__init__(
            {
                datetime: self.hook_datetime,
                time: self.hook_time,
                date: self.hook_date,
                re.Pattern: self.hook_re_pattern,
                bool: self.hook_bool,
                type(None): self.hook_none,
            }
        )

    def hook_datetime(self, v: str | datetime) -> datetime:
        return datetime.fromisoformat(v) if isinstance(v, str) else v

    def hook_time(self, v: str | time) -> time:
        return time.fromisoformat(v) if isinstance(v, str) else v

    def hook_date(self, v: str | date) -> date:
        return date.fromisoformat(v) if isinstance(v, str) else v

    def hook_re_pattern(self, v: str | re.Pattern):
        return re.compile(v) if isinstance(v, str) else v

    def hook_bool(self, v: JWrapper[bool] | bool) -> bool:
        return v.value if isinstance(v, JWrapper) else v

    def hook_none(self, v: JWrapper[None] | None) -> None:
        return v.value if isinstance(v, JWrapper) else v

    def __contains__(self, o: object) -> bool:
        if typing_extensions.get_origin(o) == Union:
            for arg in typing_extensions.get_args(o):
                if arg in self:
                    return True
        return super().__contains__(o)

    def __getitem__(self, k: Any) -> Any:
        if typing_extensions.get_origin(k) == Union:
            for arg in typing_extensions.get_args(k):
                if super().__contains__(arg):
                    return self[arg]
        return super().__getitem__(k)


_TYPE_HOOK = _KayakuDaciteTypeHook()


def from_dict(model: type[T], data: dict[str, Any]) -> T:
    return _from_dict(
        model,
        data,
        Config(
            type_hooks=_TYPE_HOOK,
            cast=[enum.Enum],
        ),
    )
