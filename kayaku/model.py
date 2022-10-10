from __future__ import annotations

from dataclasses import Field, asdict as to_dict, field
from dataclasses import dataclass, fields
from inspect import signature
from typing import TYPE_CHECKING, Callable, Tuple, Type, TypeVar, Union, cast, overload
from typing_extensions import dataclass_transform

from dacite.core import from_dict
from loguru import logger

from .doc_parse import store_field_description
from .pretty import Prettifier
from .schema_gen import ConfigModel
from .utils import update

T = TypeVar("T")


@dataclass_transform(field_specifiers=(Field, field))
def config_stub(
    domain: str,
    *,
    init=True,
    repr=True,
    eq=True,
    order=False,
    unsafe_hash=False,
    frozen=False,
    match_args=True,
    kw_only=False,
    slots=False,
) -> Callable[[type[T]], type[T]]:
    ...


def config_impl(domain: str, **kwargs) -> Callable[[type], type[ConfigModel]]:
    def wrapper(cls: type) -> type[ConfigModel]:
        from .domain import _store, insert_domain

        cls = cast(type[ConfigModel], dataclass(**kwargs)(cls))
        store_field_description(cls)
        domain_tup: Tuple[str, ...] = tuple(domain.split("."))
        if not all(domain_tup):
            raise ValueError(f"{domain!r} contains empty segment!")

        if domain_tup in _store.models:
            store = _store.models[domain_tup]
            other = store.cls
            if (
                cls.__module__ == other.__module__
                and cls.__qualname__ == other.__qualname__
            ):
                ...  # TODO: remove original occupations, inject new ones
                return cls

            raise NameError(f"{domain!r} is already occupied by {other!r}")
        insert_domain(domain_tup, cls)
        return cls

    return wrapper


config = config_stub if TYPE_CHECKING else config_impl


def create(cls: Type[T], flush: bool = False) -> T:
    """Create a model.

    Specifying `flush` will force a model-level data reload.

    Note: It's *highly* recommended that you `create` a model every time (for safe reload).
    """
    from .domain import _store

    if cls not in _store.cls_domains or not isinstance(cls, ConfigModel):
        raise  # TODO
    if flush or _store.cls_domains[cls] is None:
        from . import backend as json5

        fmt_path = _store.location_map[cls]
        document = json5.loads(fmt_path.path.read_text("utf-8"))
        container = document
        for sect in fmt_path.section:
            container = container[sect]
        _store.model_storage[cls] = from_dict(cls, container)

    return cast(T, _store.model_storage[cls])


def save(model: Union[T, Type[T]]) -> None:
    """Save a model."""
    from . import backend as json5
    from .domain import _store

    inst: ConfigModel = (
        _store.model_storage[model] if isinstance(model, type) else model
    )
    fmt_path = _store.location_map[inst.__class__]
    document = json5.loads(fmt_path.path.read_text("utf-8"))
    container = document
    for sect in fmt_path.section:
        container = container.setdefault(sect, {})
    update(container, to_dict(inst))  # TODO
    fmt_path.path.write_text(json5.dumps(Prettifier().prettify(document)), "utf-8")


def save_all() -> None:
    """Save every model in kayaku.

    Very useful if you want to sync changes on cleanup.
    """
    from . import backend as json5
    from .domain import _store, file_map

    for path, store in file_map.items():
        document = json5.loads(path.read_text("utf-8"))
        for section, classes in store.items():
            container = document
            for sect in section:
                container = container.setdefault(sect, {})
            for cls in classes:
                update(container, to_dict(_store.model_storage[cls]))  # TODO
        path.write_text(json5.dumps(Prettifier().prettify(document)), "utf-8")
