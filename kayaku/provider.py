from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import (
    TYPE_CHECKING,
    AbstractSet,
    Any,
    ClassVar,
    Dict,
    MutableMapping,
    Optional,
    Type,
    TypeVar,
    Union,
    overload,
)
from weakref import WeakValueDictionary

if TYPE_CHECKING:
    from kayaku.model import ConfigModel

    T_Model = TypeVar("T_Model", bound=ConfigModel)


class BaseProvider(ABC):
    identity: ClassVar[str]
    config: ClassVar[Optional[Type[ConfigModel]]] = None

    @abstractmethod
    def __init__(self, config: Optional[ConfigModel] = None) -> None:
        ...

    @abstractmethod
    def fetch(self, model: Type[T_Model]) -> T_Model:
        ...

    @abstractmethod
    def supported(self) -> AbstractSet[str]:
        ...

    async def apply_modifies(self, modify_data: Dict[str, Any]) -> None:
        raise NotImplementedError(f"{self.__class__!r} only supports `fetch`.")


_providers: MutableMapping[str, BaseProvider] = WeakValueDictionary()
_identity_registry: MutableMapping[str, BaseProvider] = WeakValueDictionary()


@overload
def add_provider(provider: BaseProvider) -> None:
    ...


@overload
def add_provider(
    provider: Type[BaseProvider],
    config: Union[ConfigModel, Dict[str, Any]],
) -> None:
    ...


def add_provider(
    provider: Union[BaseProvider, Type[BaseProvider]],
    config: Union[ConfigModel, Dict[str, Any], None] = None,
) -> None:
    if provider.identity in _providers:
        raise ValueError(
            f"{provider.identity!r} is already taken by {_providers[provider.identity]}"
        )
    if not isinstance(provider, BaseProvider):
        if provider.config:
            provider = provider(
                provider.config(**config) if isinstance(config, dict) else config
            )
        else:
            provider = provider(None)
    _providers[provider.identity] = provider
    for identity in provider.supported():
        _identity_registry[identity] = provider


def scan_providers(config: Dict[str, Dict[str, Any]]) -> None:
    for entry_point in entry_points(group="kayaku.providers"):
        provider_cls: Type[BaseProvider] = entry_point.load()
        if not provider_cls.config:
            add_provider(provider_cls(None))
        if provider_cls.identity in config:
            add_provider(provider_cls, config[provider_cls.identity])


def create(model: Type[T_Model]) -> T_Model:
    if not model.__identity__:
        raise ValueError(
            f"{model!r} is not creatable as it doesn't have `identity` to lookup."
        )
    identity: str = model.__identity__
    if identity not in _identity_registry:
        raise ValueError(f"No provider supports creating {model!r}")
    return _identity_registry[identity].fetch(model)


@dataclass
class ModifyContext:
    content: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    synced: bool = True
    unsafe: bool = False


modify_context: ContextVar[ModifyContext] = ContextVar("modify_context")


async def apply_modifies() -> None:
    ctx = modify_context.get()
    if not ctx.synced:
        await asyncio.wait(
            asyncio.create_task(_providers[provider_id].apply_modifies(value))
            for provider_id, value in ctx.content.items()
        )
        ctx.synced = True
        ctx.content = {}


class modify(AbstractAsyncContextManager, AbstractContextManager):
    def __init__(self, *, unsafe: bool = False) -> None:
        self.unsafe: bool = unsafe
        self.modify_token: Optional[Token[ModifyContext]] = None

    def __enter__(self) -> None:
        if self.modify_token:
            raise RuntimeError("`modify` is non-reentrant.")
        self.modify_token = modify_context.set(ModifyContext(unsafe=self.unsafe))

    async def __aenter__(self) -> None:
        return self.__enter__()

    async def __aexit__(self, *_) -> bool:  # auto commit when in async context
        current_context = modify_context.get()
        if not current_context.synced:
            await apply_modifies()
        return self.__exit__(*_)

    def __exit__(self, *_) -> bool:
        current_context = modify_context.get()
        if not current_context.synced:
            raise RuntimeError(f"Modification not synced: {current_context.content}")
        if not self.modify_token:
            raise RuntimeError
        modify_context.reset(self.modify_token)
        self.modify_token = None
        return False
