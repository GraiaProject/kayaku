from __future__ import annotations

import inspect
from dataclasses import MISSING, Field, asdict, is_dataclass
from typing import Union, cast

from .backend.types import Array, BlockStyleComment, JObject, JString, JType, convert
from .schema_gen import ConfigModel


def remove_generated_comment(obj: JType):
    obj.json_before = [wsc for wsc in obj.json_before if "@type" not in wsc]
    obj.json_after = [wsc for wsc in obj.json_after if "@type" not in wsc]
    if isinstance(obj, (JObject, Array)):
        obj.json_container_tail = [
            wsc for wsc in obj.json_container_tail if "@type" not in wsc
        ]


def gen_field_doc(field: Field, doc: str | None) -> str:
    type_repr = f"@type: {inspect.formatannotation(field.type)}"
    return f"{doc}\n\n{type_repr}" if doc else type_repr


def format_exist(
    fields: dict[str, tuple[Field, str | None]],
    container: JObject,
) -> None:
    for k, v in container.items():
        if k in fields:
            field, doc = fields.pop(k)
            k: JString = convert(k)
            container[k] = convert(v)
            remove_generated_comment(k)
            remove_generated_comment(v)
            k.json_before.append(BlockStyleComment(gen_field_doc(field, doc)))


def format_not_exist(
    fields: dict[str, tuple[Field, str | None]],
    container: JObject,
) -> None:
    remove_generated_comment(container)
    for k, (field, doc) in fields.items():
        k = convert(k)
        if field.default_factory is not MISSING:
            default = field.default_factory()
        else:
            default = field.default
        if is_dataclass(default):
            v = asdict(default)
        elif default is MISSING:
            v = None
        else:
            v = default
        container[k] = convert(v)
        k.json_before.append(BlockStyleComment(gen_field_doc(field, doc)))


def format_with_model(container: JObject, model: type[ConfigModel]) -> None:
    if not isinstance(container, JObject):
        raise TypeError(f"{container} is not a json object.")

    fields = {
        k: (f, cast(Union[str, None], f.metadata.get("description")))
        for k, f in model.__dataclass_fields__.items()
    }
    format_exist(fields, container)
    format_not_exist(fields, container)
