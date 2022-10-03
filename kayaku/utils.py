from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, create_model
from typing_extensions import TypeAlias

from dc_schema import get_schema

from .backend.types import Array, JObject
from .model import ConfigModel

DomainType: TypeAlias = "tuple[str, ...]"


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


# FIXME: description
def gen_schema(models: list[tuple[DomainType, type[ConfigModel]]]) -> dict:

    # Create a temporary model to contain *every* model in the file.
    temp_model = create_model(
        "KayakuJSONSchema",
        **{
            f"kayaku::{model.__module__}.{model.__qualname__}": (
                model,
                Field(..., alias=f"{model.__module__}.{model.__qualname__}"),
            )
            for _, model in models
        },
    )
    generated_schema = temp_model.schema(by_alias=True, ref_template="#/$defs/{model}")
    qualname_ref_map: dict = generated_schema["properties"]
    definitions: dict = generated_schema["definitions"]
    # Generate a new schema
    schema: dict[str, Any] = {
        "$schema": "http://json-schema.org/schema",
        "type": "object",
    }
    for domains, model in models:
        container: dict = schema
        for d in domains:
            container = container.setdefault("properties", {}).setdefault(
                d, {"type": "object"}
            )
        container.update(qualname_ref_map[f"{model.__module__}.{model.__qualname__}"])
    schema["$defs"] = definitions
    return schema
