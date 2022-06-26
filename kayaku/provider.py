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
    List,
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
    name: ClassVar[str]
    config: ClassVar[Optional[Type[ConfigModel]]] = None

    @abstractmethod
    def __init__(self, config: Optional[ConfigModel] = None) -> None:
        ...

    @abstractmethod
    def fetch(self, model: Type[T_Model]) -> T_Model:
        ...

    @property
    @abstractmethod
    def supported_identities(self) -> AbstractSet[str]:
        ...

    async def apply_modifies(self, identity: str, data: Dict[str, Any]) -> None:
        raise NotImplementedError(f"{self.__class__!r} only supports `fetch`.")


_provider_registry: MutableMapping[str, Type[BaseProvider]] = WeakValueDictionary()
_model_registry: MutableMapping[str, BaseProvider] = WeakValueDictionary()


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
    if not isinstance(provider, BaseProvider):
        if provider.config:
            provider = provider(
                provider.config(**config) if isinstance(config, dict) else config
            )
        else:
            provider = provider(None)
    provider_cls = provider.__class__
    provider_id = provider_cls.name
    if (
        provider_id in _provider_registry
        and _provider_registry[provider_id] is not provider_cls
    ):
        raise ValueError(
            f"{provider_id!r} is already taken by {_provider_registry[provider_id]}"
        )
    _provider_registry[provider_id] = provider_cls
    for identity in provider.supported_identities:
        _model_registry[identity] = provider


def scan_providers(config: Dict[str, List[Dict[str, Any]]]) -> None:
    for entry_point in entry_points(group="kayaku.providers"):
        provider_cls: Type[BaseProvider] = entry_point.load()
        if not provider_cls.config:
            add_provider(provider_cls(None))
        if provider_cls.name in config:
            for provider_cfg in config[provider_cls.name]:
                add_provider(provider_cls, provider_cfg)


def create(model: Type[T_Model]) -> T_Model:
    if not model.__identity__:
        raise ValueError(
            f"{model!r} is not creatable as it doesn't have `identity` to lookup."
        )
    identity: str = model.__identity__
    if identity not in _model_registry:
        raise ValueError(f"No provider supports creating {model!r}")
    return _model_registry[identity].fetch(model)


@dataclass
class ModifyContext:
    content: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    unsafe: bool = False


modify_context: ContextVar[ModifyContext] = ContextVar("modify_context")


async def apply_modifies() -> None:
    ctx = modify_context.get()


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
        ctx = modify_context.get()
        if ctx.content:
            await asyncio.wait(
                asyncio.create_task(
                    _model_registry[identity].apply_modifies(identity, data)
                )
                for identity, data in ctx.content.items()
            )
        ctx.content = {}
        return self.__exit__(*_)

    def __exit__(self, *_) -> bool:
        current_context = modify_context.get()
        if current_context.content:
            raise RuntimeError(f"Modification not synced: {current_context.content}")
        if not self.modify_token:
            raise RuntimeError("`modify` is not triggered via `with`.")
        modify_context.reset(self.modify_token)
        self.modify_token = None
        return False
