from __future__ import annotations

import contextlib
import inspect
from typing import Iterable

from pydantic import BaseModel
from pydantic.fields import ModelField

from .backend.types import (
    WSC,
    Array,
    BlockStyleComment,
    Comment,
    Container,
    HashStyleComment,
    JSONType,
    LineStyleComment,
    Object,
    WhiteSpace,
    convert,
)
from .doc_parse import extract_field_docs


def format_wsc(origin: list[WSC]) -> None:
    new: list[WSC] = []
    origin_iter = iter(origin)
    for wsc in origin_iter:
        if isinstance(wsc, Comment):
            new.append(wsc)

        if new and (
            isinstance(new[-1], Comment)
            or (isinstance(new[-1], WhiteSpace) and "\n" not in new[-1])
        ):
            new.append(WhiteSpace("\n"))
    origin.clear()
    origin.extend(new)


def _parse_wsc(wsc_iter: Iterable[WSC]) -> set[str]:
    return {str(wsc).strip() for wsc in wsc_iter if isinstance(wsc, Comment)}


def _collect_comments(obj: JSONType) -> set[str]:
    res: set[str] = set()
    res.update(_parse_wsc(obj.json_before))
    res.update(_parse_wsc(obj.json_after))
    if isinstance(obj, Container):
        res.update(_parse_wsc(obj.json_container_head))
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


def _format_exist(
    fields: dict[str, tuple[ModelField, str | None]],
    container: Object,
) -> None:
    for k, v in list(container.items()):
        if k in fields:
            field, doc = fields.pop(k)
            conv_v = convert(v)
            if conv_v is not v:
                container[k] = conv_v
            exclude = _collect_comments(conv_v)
            type_repr = f"type: {dict(field.__repr_args__())['type']}"
            if type_repr not in exclude:
                conv_v.json_after.append(
                    LineStyleComment(type_repr)
                )  # TODO: format choice

            if doc and (d := inspect.cleandoc(doc)) not in exclude:
                conv_v.json_after.append(BlockStyleComment(d))
            format_wsc(conv_v.json_after)


def _format_not_exist(
    fields: dict[str, tuple[ModelField, str | None]],
    container: Object,
) -> None:
    exclude = _collect_comments(container)
    for k, (field, doc) in fields.items():
        type_comment = f"type: {dict(field.__repr_args__())['type']}"
        if not field.required:
            v = convert(
                field.default.dict(by_alias=True)
                if isinstance(field.default, BaseModel)
                else field.default
            )
            container[k] = v
            if type_comment not in exclude:
                v.json_after.append(LineStyleComment(type_comment))
            format_wsc(v.json_after)
            if doc and (d := inspect.cleandoc(doc)) not in exclude:
                v.json_after.append(BlockStyleComment(d))
        else:
            hint = LineStyleComment(
                f'"{k}": ... # {type_comment}'
            )  # TODO: format choice
            if hint not in exclude:
                container.json_container_tail.append(hint)
            if doc and (d := inspect.cleandoc(doc)) not in exclude:
                container.json_container_tail.append(BlockStyleComment(d))
        format_wsc(container.json_container_tail)


def format_with_model(container: Object, model: type[BaseModel]) -> None:
    if not isinstance(container, Object):
        raise TypeError(f"{container} is not a json object.")
    fields: dict[str, tuple[ModelField, str | None]] = extract_field_docs(model)
    _format_exist(fields, container)
    _format_not_exist(fields, container)
