from __future__ import annotations

from dataclasses import dataclass, fields
from inspect import signature
from typing import TYPE_CHECKING, Callable, Tuple, Type, TypeVar, Union, cast

from attrs import define
from loguru import logger
from pydantic import BaseConfig, BaseModel, Extra
from pydantic.utils import generate_model_signature

from .doc_parse import store_field_description
from .pretty import Prettifier
from .utils import update

if TYPE_CHECKING:
    from .model import ConfigModel


def config(cls=None, /, *, domain: str, **kwargs):
    def wrapper(cls: type) -> type[ConfigModel]:
        from .domain import _reg, domain_map, file_map

        cls = cast(type[ConfigModel], dataclass(cls, **kwargs))

        domain_tup: Tuple[str, ...] = tuple(domain.split("."))
        if not all(domain_tup):
            raise ValueError(f"{domain!r} contains empty segment!")

        if domain_tup in domain_map:
            other = domain_map[domain_tup]
            if (
                cls.__module__ == other.__module__
                and cls.__qualname__ == other.__qualname__
            ):
                if fields(cls) != fields(other):
                    logger.warning(f"{cls} changed signature!")
                    logger.warning(f"From: {signature(other)}")
                    logger.warning(f"To  : {signature(cls)}")
                    logger.warning(
                        "This change will not reflect in your schema or comments until next initialization!"
                    )
                domain_map[domain_tup] = cls
                _reg.model_map.pop(other)
                fmt_path = _reg.model_path.pop(other)
                _reg.model_path[cls] = fmt_path
                file_map[fmt_path.path][tuple(fmt_path.section)].remove(other)
                file_map[fmt_path.path][tuple(fmt_path.section)].append(cls)
                create(cls, flush=True)
                return cls

            raise NameError(f"{domain!r} is already occupied by {other!r}")
        domain_map[domain_tup] = cls
        if _reg.initialized:
            raise RuntimeError(
                f"kayaku is already fully initialized, adding {cls} is not allowed."
            )
        else:
            _reg.postponed.append(domain_tup)
        store_field_description(cls)

        return cls

    return wrapper if cls is None else wrapper(cls)


T_Model = TypeVar("T_Model", bound=ConfigModel)


def create(cls: Type[T_Model], flush: bool = False) -> T_Model:
    """Create a model.

    Specifying `flush` will force a model-level data reload.

    Note: It's *highly* recommended that you `create` a model every time (for safe reload).
    """
    from .domain import _reg

    if flush:
        from . import backend as json5

        fmt_path = _reg.model_path[cls]
        document = json5.loads(fmt_path.path.read_text("utf-8"))
        container = document
        for sect in fmt_path.section:
            container = container[sect]
        _reg.model_map[cls] = cls.parse_obj(container)

    return cast(T_Model, _reg.model_map[cls])


def save(model: Union[T_Model, Type[T_Model]]) -> None:
    """Save a model."""
    from . import backend as json5
    from .domain import _reg

    inst: ConfigModel = _reg.model_map[model] if isinstance(model, type) else model
    fmt_path = _reg.model_path[inst.__class__]
    document = json5.loads(fmt_path.path.read_text("utf-8"))
    container = document
    for sect in fmt_path.section:
        container = container.setdefault(sect, {})
    update(container, inst.dict(by_alias=True))
    fmt_path.path.write_text(json5.dumps(Prettifier().prettify(document)), "utf-8")


def save_all() -> None:
    """Save every model in kayaku.

    Very useful if you want to reflect changes on cleanup.
    """
    from . import backend as json5
    from .domain import _reg, file_map

    for path, store in file_map.items():
        document = json5.loads(path.read_text("utf-8"))
        for section, classes in store.items():
            container = document
            for sect in section:
                container = container.setdefault(sect, {})
            for cls in classes:
                update(container, _reg.model_map[cls].dict(by_alias=True))
        path.write_text(json5.dumps(Prettifier().prettify(document)), "utf-8")
