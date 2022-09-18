from __future__ import annotations

from typing import Any

from .backend.types import Array, Container, Object


def update(container: Container, data: Any):
    if container == data:
        return
    if isinstance(container, Object):
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
