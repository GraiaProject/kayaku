from __future__ import annotations

import enum
import re
import types
from dataclasses import field, fields
from datetime import date, datetime, time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence, TypeVar, Union

import typing_extensions
from dacite.config import Config
from dacite.core import from_dict as _from_dict

from .backend.types import Array, JContainer, JObject, JType, JWrapper, convert
from .schema_gen import DataClass

DC_T = TypeVar("DC_T", bound=DataClass)
T = TypeVar("T")


def copy_meta(src: Any, dst: JType):
    if isinstance(dst, JContainer):
        dst.json_container_tail = getattr(
            src, "json_container_tail", dst.json_container_tail
        )
    dst.json_before = getattr(src, "json_before", dst.json_before)
    dst.json_after = getattr(src, "json_after", dst.json_after)


def _update_array(container: Array, data: list):
    for i in range(len(container)):
        val = container[i]
        if isinstance(val, (DataClass, dict)):
            new_container = JObject()
            update(new_container, val, delete=True)
            val = new_container
        elif isinstance(val, (re.Pattern, date, datetime, time)):
            val = convert(
                val.pattern if isinstance(val, re.Pattern) else val.isoformat()
            )
        elif isinstance(val, enum.Enum):
            val = convert(val.value)
        elif isinstance(val, Sequence) and not isinstance(val, str):
            val: JType = convert(val if isinstance(val, list) else list(val))
            _update_array(val, [])
        else:
            val = convert(val)

        if i < len(data) and isinstance(data[i], JType):
            copy_meta(data[i], val)
        container[i] = val
    if len(container) < len(data):
        container.json_container_trailing_comma = True


def update(container: JObject, data: DataClass | dict, delete: bool = False):
    if isinstance(data, DataClass):
        k_v_pairs = {f.name: getattr(data, f.name) for f in fields(data)}
    else:
        k_v_pairs = data
    to_be_popped: set[str] = set(container.keys() if delete else ())
    for k, v in k_v_pairs.items():
        k = convert(k)
        to_be_popped.discard(k)
        origin_v = container.get(k, None)
        if isinstance(v, (DataClass, dict)):
            new_v = container.setdefault(k, JObject())
            update(new_v, v, delete=True)
            v = new_v
        elif isinstance(v, (re.Pattern, date, datetime, time)):
            v = convert(v.pattern if isinstance(v, re.Pattern) else v.isoformat())
        elif isinstance(v, enum.Enum):
            v = convert(v.value)
        elif isinstance(v, Sequence) and not isinstance(v, str):
            v: JType = convert(v if isinstance(v, list) else list(v))
            _update_array(v, origin_v or [])
        else:
            v: JType = convert(v)
        if origin_v is not None:
            copy_meta(origin_v, v)
        container[k] = v
    for k in to_be_popped:
        container.pop(k, None)


Unions = {Union, typing_extensions.Union, types.UnionType}


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
                None: self.hook_none,
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
        if typing_extensions.get_origin(o) in Unions:
            return any(
                dict.__contains__(self, arg) for arg in typing_extensions.get_args(o)
            )
        return super().__contains__(o)

    def __getitem__(self, k: Any) -> Any:
        if typing_extensions.get_origin(k) in Unions:

            def applier(arg):
                for func in [
                    self[arg]
                    for arg in typing_extensions.get_args(k)
                    if dict.__contains__(self, arg)
                ]:
                    arg = func(arg)
                return arg

            return applier
        return super().__getitem__(k)


_TYPE_HOOK = _KayakuDaciteTypeHook()


def from_dict(model: type[DC_T], data: dict[str, Any]) -> DC_T:
    return _from_dict(
        model,
        data,
        Config(
            type_hooks=_TYPE_HOOK,
            cast=[enum.Enum],
        ),
    )


if not TYPE_CHECKING:

    def copying_field_impl(default, **kwargs):
        from copy import deepcopy

        default_value = deepcopy(default)
        return field(default_factory=lambda: deepcopy(default_value), **kwargs)


copying_field = field if TYPE_CHECKING else copying_field_impl


def to_path(path: str, suffix: str) -> Path:
    return Path(path).expanduser().resolve().with_suffix(suffix)


def touch_path(pth: Path) -> Path:
    # create parent dir if not exist
    pth.parent.mkdir(parents=True, exist_ok=True)
    pth.touch(exist_ok=True)
    return pth
