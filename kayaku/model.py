from __future__ import annotations

import sys
from dataclasses import Field, dataclass, field
from dataclasses import fields as get_fields
from typing import TYPE_CHECKING, Callable, Tuple, Type, TypeVar, Union, cast

from dacite.core import from_dict
from loguru import logger
from typing_extensions import dataclass_transform

from .backend import dumps, loads
from .backend.types import JObject
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
    """将类型转换为 kayaku 承认的设置类。

    `domain` 以外的参数将被直接传入 [`dataclasses.dataclass`][dataclasses.dataclass] 进行转换。

    Args:
        domain (str): *唯一的* 用于标识类的结构位置与类别的字符串，用 `.` 分开。

        init (bool, optional): If true (the default), a __init__() method will be generated.
        repr (bool, optional): If true (the default), a __repr__() method will be generated.
        eq (bool, optional): If true (the default), an __eq__() method will be generated.
        order (bool, optional): If specified, __lt__(), __le__(), __gt__(), and __ge__() methods will be generated.
        unsafe_hash (bool, optional): Force dataclass() to create a __hash__() method. Otherwise a __hash__() method is generated according to how eq and frozen are set.
        frozen (bool, optional): If specified, assigning to fields will generate an exception. This emulates read-only frozen instances.
        match_args (bool, optional): If true (the default is True), the __match_args__ tuple will be created from the list of parameters to the generated __init__().
        kw_only (bool, optional): If specified, then all fields will be marked as keyword-only.
        slots (bool, optional): If specified, __slots__ attribute will be generated and new class will be returned instead of the original one.
    Returns:
        类的装饰器。
    """
    ...


def config_impl(domain: str, **kwargs) -> Callable[[type], Type[ConfigModel]]:
    def wrapper(cls: type) -> type[ConfigModel]:
        from . import domain as domain_mod

        if not hasattr(domain_mod, "_store"):
            raise RuntimeError("You cannot call `config` before initialization!")
        from .domain import _store as g_store
        from .domain import insert_domain

        cls = cast(Type[ConfigModel], dataclass(**kwargs)(cls))
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
                    if (
                        sys.getrefcount(instance) > 3
                    ):  # parameter, local var `instance`, `m_store.instance`
                        logger.warning(f"Instance of {other!r} is stilled referred!")
                    m_store.instance = None
                f_store = g_store.files[m_store.location.path]
                # remove original occupations

                g_store.cls_domains.pop(other)
                other_def_name = f_store.generator.retrieve_name(other)
                other_schema = f_store.generator.defs.pop(other_def_name)
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
    """创建对应的模型。

    给 `flush` 传入真值会强制重载。

    Note:
        为了安全重载，我们推荐你让返回的实例存活时间尽量短。
    """

    from .domain import _store

    if not (issubclass(cls, ConfigModel) and cls in _store.cls_domains):
        raise TypeError(f"{cls!r} is not a registered ConfigModel class!")
    domain = _store.cls_domains[cls]
    model_store = _store.models[domain]
    if flush or model_store.instance is None:

        fmt_path = model_store.location
        document = loads(fmt_path.path.read_text("utf-8") or "{}")
        container = document
        for sect in fmt_path.mount_dest:
            container = container.setdefault(sect, JObject())
        model_store.instance = from_dict(cls, container)

    return cast(T, model_store.instance)


def save(model: Union[T, Type[T]]) -> None:
    """保存某个类的设置。 对应的 JSON Schema 也会被更新。"""
    from .domain import _store

    cls = cast(Type[ConfigModel], model if isinstance(model, type) else model.__class__)
    m_store = _store.models[_store.cls_domains[cls]]
    inst = m_store.instance
    if inst is not None:
        document = loads(m_store.location.path.read_text("utf-8") or "{}")
        container = document
        for sect in m_store.location.mount_dest:
            container = container.setdefault(sect, JObject())
        update(container, inst)
        document.pop("$schema", None)
        document["$schema"] = m_store.location.path.with_suffix(".schema.json").as_uri()
        m_store.location.path.write_text(
            dumps(_store.prettifier.prettify(document), endline=True), "utf-8"
        )
    m_store.location.path.with_suffix(".schema.json").write_text(
        dumps(_store.files[m_store.location.path].get_schema()), "utf-8"
    )
