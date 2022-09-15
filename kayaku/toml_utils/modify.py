from __future__ import annotations

from typing import Any

from tomlkit.container import Container
from tomlkit.items import AbstractTable, AoT, Array, InlineTable, Item, Trivia, item


def update_array_like(item: AoT | Array, data: list) -> None:
    ...


def update_from_model(origin: Any, data: dict) -> None:
    if isinstance(origin, AbstractTable):
        origin.trivia.trail = origin.trivia.trail or "\n"
        container = origin.value
    elif isinstance(origin, Container):
        container = origin
    else:
        raise TypeError(f"{origin} is not a valid container!")
    for key, val in data.items():
        if key in container:
            i = container[key]
            if isinstance(val, dict):
                assert isinstance(
                    i, (AbstractTable, Container)
                ), f"{i} is not a container!"
                update_from_model(i, val)
            if isinstance(val, list):  # Array / AoT
                assert isinstance(i, (Array, AoT))
                update_array_like(i, val)
            else:  # regular item
                assert isinstance(i, Item), f"{i} is not regular item!"
                new_item: Item = item(val)
                new_item.trivia.__dict__ = i.trivia.__dict__
                container[key] = new_item
        elif isinstance(val, dict) and isinstance(origin, InlineTable):
            il_table = InlineTable(Container(), Trivia(), False)
            container[key] = il_table
            update_from_model(il_table, val)
        else:
            container[key] = item(val)
