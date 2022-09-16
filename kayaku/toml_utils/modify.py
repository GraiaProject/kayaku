from __future__ import annotations

from typing import Any

from tomlkit.api import array, table
from tomlkit.container import Container
from tomlkit.items import (
    AbstractTable,
    AoT,
    Array,
    Comment,
    InlineTable,
    Item,
    Null,
    Trivia,
    Whitespace,
    item,
)


def update_array_like(container: AoT | Array, data: list) -> None:
    if container.unwrap() == data:
        return
    if isinstance(container, AoT):
        new_body = []
        if not all(isinstance(i, dict) for i in data):
            raise TypeError(f"{data} is inappropriate for array of tables!")
        for i, v in enumerate(data):
            if container[i].unwrap() == v:
                new_body.append(container[i])
            else:
                new_body.append(table(v))
    else:
        comments = []
        for body in container._value:
            if body.comment:
                comments.append(Whitespace("\n"))
                if isinstance(body.value, Null):
                    comments.append(body.comment)
                else:
                    comments.append(
                        Comment(
                            Trivia(
                                comment=f"# {body.value} {body.comment.trivia.comment}"
                            )
                        )
                    )
        arr = Array(
            comments,
            container.trivia,
            bool(comments),
        )
        [arr.append(v) for v in data]
        container.__dict__.update(arr.__dict__)


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
