from __future__ import annotations

import inspect
from typing import Iterable

from pydantic import BaseModel
from pydantic.fields import ModelField

from kayaku.pretty import Prettifier

from .backend.types import (
    WSC,
    Array,
    BlockStyleComment,
    Comment,
    JContainer,
    JObject,
    JString,
    JType,
    convert,
)


def _parse_wsc(wsc_iter: Iterable[WSC]) -> set[str]:
    return {
        "\n".join(Prettifier.clean_comment(inspect.cleandoc(wsc).splitlines()))
        for wsc in wsc_iter
        if isinstance(wsc, Comment)
    }


def _collect_comments(obj: JType) -> set[str]:
    res: set[str] = set()
    res.update(_parse_wsc(obj.json_before))
    res.update(_parse_wsc(obj.json_after))
    if isinstance(obj, (JObject, Array)):
        res.update(_parse_wsc(obj.json_container_tail))
        if isinstance(obj, JObject):
            for k, v in obj.items():
                res.update(_collect_comments(k) if isinstance(k, JType) else set())
                res.update(_collect_comments(v) if isinstance(v, JType) else set())
        else:
            for v in obj:
                res.update(_collect_comments(v) if isinstance(v, JType) else set())
    return res


def gen_field_doc(field: ModelField, doc: str | None) -> str:
    type_repr = f"@type: {dict(field.__repr_args__())['type']}"
    return f"{doc}\n\n{type_repr}" if doc else type_repr


def format_exist(
    fields: dict[str, tuple[ModelField, str | None]],
    container: JObject,
) -> None:
    for k, v in list(container.items()):
        if k in fields:
            field, doc = fields.pop(k)
            k: JString = convert(k)
            conv_v: JType = convert(v)
            container[k] = conv_v
            exclude = _collect_comments(k)
            if (d := gen_field_doc(field, doc)) not in exclude:
                k.json_before.append(BlockStyleComment(d))


def format_not_exist(
    fields: dict[str, tuple[ModelField, str | None]],
    container: JObject,
) -> None:
    exclude = _collect_comments(container)
    for k, (field, doc) in fields.items():
        k = convert(k)
        v = convert(
            field.default.dict(by_alias=True)
            if isinstance(field.default, BaseModel)
            else field.default
        )
        container[k] = v
        if (d := gen_field_doc(field, doc)) not in exclude:
            k.json_before.append(BlockStyleComment(d))


def format_with_model(container: JObject, model: type[BaseModel]) -> None:
    if not isinstance(container, JObject):
        raise TypeError(f"{container} is not a json object.")
    fields: dict[str, tuple[ModelField, str | None]] = {
        k: (f, f.field_info.description) for k, f in model.__fields__.items()
    }
    format_exist(fields, container)
    format_not_exist(fields, container)
