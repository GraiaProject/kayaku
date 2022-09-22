from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, create_model

from .backend.types import Array, JContainer, JObject


def update(container: JContainer, data: Any):
    if container == data:
        return
    if isinstance(container, JObject):
        assert isinstance(data, dict)
        for k, v in data.items():
            if k in container and isinstance(v, (list, dict)):
                update(container[k], v)
            else:
                container[k] = v
    elif isinstance(container, Array):
        assert isinstance(data, (list, tuple))
        if len(data) > len(container):
            container.extend(None for _ in range(len(data) - len(container)))
        else:
            [container.pop() for _ in range(len(container) - len(data))]
        for (i, v) in enumerate(data):
            if (c := container[i]) != v:
                if isinstance(c, v.__class__) and isinstance(v, (list, dict)):
                    update(c, v)
                else:
                    container[i] = v


def gen_schema(models: list[tuple[tuple[str, ...], type[BaseModel]]]) -> dict:
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
    # Generate a temporary schema. We only need the "properties" and "definitions" part.
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
