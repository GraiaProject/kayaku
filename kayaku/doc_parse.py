from __future__ import annotations

import ast
import inspect
import sys
from typing import cast

from pydantic import BaseModel
from pydantic.fields import ModelField


def cleanup_src(src: str) -> str:
    lines = src.expandtabs().split("\n")
    margin = len(lines[0]) - len(lines[0].lstrip())
    for i in range(len(lines)):
        lines[i] = lines[i][margin:]
    return "\n".join(lines)


def extract_field_docs(
    cls: type[BaseModel],
) -> dict[str, tuple[ModelField, str | None]]:
    node: ast.ClassDef = cast(
        ast.ClassDef, ast.parse(cleanup_src(inspect.getsource(cls))).body[0]
    )
    doc_store: dict[str, str] = {}
    for i, stmt in enumerate(node.body):
        name: str | None = None
        if (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
        ):
            name = stmt.targets[0].id
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            name = stmt.target.id
        if (
            name in cls.__fields__
            and i + 1 < len(node.body)
            and isinstance((doc_expr := node.body[i + 1]), ast.Expr)
            and isinstance((doc_const := doc_expr.value), ast.Constant)
            and isinstance(doc_string := doc_const.value, str)
        ):
            doc_store[name] = doc_string
    return {k: (v, doc_store.get(k)) for k, v in cls.__fields__.items()}
