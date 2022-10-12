from __future__ import annotations

import gc
from dataclasses import Field, dataclass, field
from dataclasses import fields as get_fields
from typing import TYPE_CHECKING, Callable, Tuple, Type, TypeVar, Union, cast

from dacite.core import from_dict
from loguru import logger
from typing_extensions import dataclass_transform

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
        from .domain import _store as g_store
        from .domain import insert_domain

        cls = cast(type[ConfigModel], dataclass(**kwargs)(cls))
        store_field_description(cls)
        domain_tup: Tuple[str, ...] = tuple(domain.split("."))
        if not all(domain_tup):
            raise ValueError(f"{domain!r} contains empty segment!")

        if domain_tup in g_store.models:
            m_store = g_store.models[domain_tup]
            other = m_store.cls
            if (
                cls.__module__ == other.__module__
                and cls.__qualname__ == other.__qualname__
            ):
                if m_store.instance is not None:
                    instance = m_store.instance
                    if len(gc.get_referrers(instance)) > 1:
                        logger.warning(f"Instance of {other!r} is stilled referred!")
                    m_store.instance = None
                f_store = g_store.files[m_store.location.path]
                # remove original occupations

                g_store.cls_domains.pop(other)
                other_def_name = f_store.generator.retrieve_name(other)
                other_schema = f_store.generator.defs.pop(other_def_name)
                g_store.cls_domains.pop(other)
                mount_dest = tuple(m_store.location.mount_dest)
                for field in get_fields(other):
                    sub_dest = mount_dest + (field.name,)
                    f_store.field_mount_record.remove(sub_dest)

                # inject new ones
                insert_domain(domain_tup, cls)
                cls_def_name = f_store.generator.retrieve_name(cls)
                cls_schema = f_store.generator.defs[cls_def_name]
                if cls_schema != other_schema:
                    logger.warning(f"Schema of {cls} has changed!")
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

    if not issubclass(cls, ConfigModel):
        raise TypeError(f"{cls!r} is not a ConfigModel class!")
    if cls not in _store.cls_domains:
        raise NameError(f"{cls!r} is not registered ConfigModel!")
    domain = _store.cls_domains[cls]
    model_store = _store.models[domain]
    if flush or model_store.instance is None:
        from . import backend as json5

        fmt_path = model_store.location
        document = json5.loads(fmt_path.path.read_text("utf-8") or "{}")
        container = document
        for sect in fmt_path.mount_dest:
            container = container.get(sect, {})
        model_store.instance = from_dict(cls, container)

    return cast(T, model_store.instance)


def save(model: Union[T, Type[T]]) -> None:
    """Save a model. Associated schema will be updated as well."""
    from . import backend as json5
    from .domain import _store

    cls = cast(Type[ConfigModel], model if isinstance(model, type) else model.__class__)
    m_store = _store.models[_store.cls_domains[cls]]
    inst = m_store.instance
    if inst is not None:
        document = json5.loads(m_store.location.path.read_text("utf-8") or "{}")
        container = document
        for sect in m_store.location.mount_dest:
            container = container.setdefault(sect, {})
        update(container, inst)
        m_store.location.path.write_text(
            json5.dumps(Prettifier().prettify(document)), "utf-8"
        )
    m_store.location.path.with_suffix(".schema.json").write_text(
        json5.dumps(_store.files[m_store.location.path].get_schema()), "utf-8"
    )
