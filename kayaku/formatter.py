from __future__ import annotations

import inspect

from pydantic import BaseModel
from pydantic.fields import ModelField
from pydantic.typing import display_as_type
from tomlkit import comment
from tomlkit.container import Container
from tomlkit.items import AbstractTable, Comment, Item, Key, SingleKey, item

from .doc_parse import extract_field_docs


def _doc_comment(
    body: list[tuple[Key | None, Item]], doc_string: str, comments: set[str]
) -> None:
    body.extend(
        [
            (None, comment(d))
            for d in inspect.cleandoc(doc_string).splitlines(False)
            if f"# {d}" not in comments
        ]
    )


def _format_exist(
    fields: dict[str, tuple[ModelField, str | None]],
    origin: Container,
    body: list[tuple[Key | None, Item]],
) -> None:
    field_comments: set[str] = set()
    for _, doc in fields.values():
        if doc:
            field_comments.update(
                f"# {d}" for d in inspect.cleandoc(doc).splitlines(False)
            )
    for k, v in origin.body:
        if k is None and (
            not isinstance(v, Comment) or v.trivia.comment not in field_comments
        ):
            body.append((k, v))
        elif k and k.key in fields:
            field, doc = fields.pop(k.key)
            if not v.trivia.comment:
                v.comment(f"type: {display_as_type(field.type_)}")
            body.append((k, v))
            if doc:
                _doc_comment(body, doc, set())


def _format_not_exist(
    fields: dict[str, tuple[ModelField, str | None]],
    body: list[tuple[Key | None, Item]],
) -> None:
    body_comments: set[str] = {
        i[1].trivia.comment for i in body if isinstance(i[1], Comment)
    }
    for k, (field, doc) in fields.items():
        type_comment = f"# type: {display_as_type(field.type_)}"
        if not field.required:
            i: Item = item(field.default)
            i.comment(type_comment)
            body.append((SingleKey(k), i))
        else:
            i: Item = comment(f"{k} = ... {type_comment}")
            if i.trivia.comment not in body_comments:
                body.append((None, i))
        if doc and doc not in body_comments:
            _doc_comment(body, doc, body_comments)


def format_with_model(
    container: Container | AbstractTable, model: type[BaseModel]
) -> None:
    if not isinstance(container, (Container, AbstractTable)):
        raise TypeError(f"{container} is not a container or a table.")
    if isinstance(container, AbstractTable):
        container.trivia.trail = container.trivia.trail or "\n"
        container = container.value
    fields: dict[str, tuple[ModelField, str | None]] = extract_field_docs(model)
    body: list[tuple[Key | None, Item]] = []
    _format_exist(fields, container, body)
    _format_not_exist(fields, body)
    container.body.clear()
    container.body.extend(body)
