from __future__ import annotations

import inspect
from typing import Iterable

from loguru import logger
from pydantic import BaseModel
from pydantic.fields import ModelField

from .backend.types import (
    WSC,
    Array,
    BlockStyleComment,
    Comment,
    Container,
    JSONType,
    Object,
    String,
    convert,
)


def clean_comment(comment: str) -> list[str]:
    res = []
    for i in inspect.cleandoc(comment).splitlines():
        if i[:2] == "* ":
            res.append(i[2:])
        elif i == "*":
            res.append("")
        else:
            res.append(i)
    return res


def _parse_wsc(wsc_iter: Iterable[WSC]) -> set[str]:
    return {
        "\n".join(clean_comment(wsc)) for wsc in wsc_iter if isinstance(wsc, Comment)
    }


def _collect_comments(obj: JSONType) -> set[str]:
    res: set[str] = set()
    res.update(_parse_wsc(obj.json_before))
    res.update(_parse_wsc(obj.json_after))
    if isinstance(obj, Container):
        res.update(_parse_wsc(obj.json_container_tail))
        if isinstance(obj, Object):
            for k, v in obj.items():
                if isinstance(k, JSONType):
                    res.update(_collect_comments(k))
                if isinstance(v, JSONType):
                    res.update(_collect_comments(v))
        elif isinstance(obj, Array):
            for v in obj:
                if isinstance(v, JSONType):
                    res.update(_collect_comments(v))
    return res


def gen_field_doc(field: ModelField, doc: str | None) -> str:
    type_repr = f"@type: {dict(field.__repr_args__())['type']}"
    return f"{doc}\n\n{type_repr}" if doc else type_repr


def format_exist(
    fields: dict[str, tuple[ModelField, str | None]],
    container: Object,
) -> None:
    for k, v in list(container.items()):
        if k in fields:
            field, doc = fields.pop(k)
            k: String = convert(k)
            conv_v: JSONType = convert(v)
            if conv_v is not v:
                container[k] = conv_v
            exclude = _collect_comments(k)
            if (d := gen_field_doc(field, doc)) not in exclude:
                k.json_before.append(BlockStyleComment(d))


def format_not_exist(
    fields: dict[str, tuple[ModelField, str | None]],
    container: Object,
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


def format_with_model(container: Object, model: type[BaseModel]) -> None:
    if not isinstance(container, Object):
        raise TypeError(f"{container} is not a json object.")
    fields: dict[str, tuple[ModelField, str | None]] = {
        k: (f, f.field_info.description) for k, f in model.__fields__.items()
    }
    format_exist(fields, container)
    format_not_exist(fields, container)
