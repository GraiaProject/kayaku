from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    AbstractSet,
    Any,
    ClassVar,
    Dict,
    List,
    MutableMapping,
    MutableSet,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)
from weakref import WeakSet, WeakValueDictionary

from importlib_metadata import entry_points
from typing_extensions import Required, TypedDict

if TYPE_CHECKING:
    from kayaku.model import ConfigModel

    T_Model = TypeVar("T_Model", bound=ConfigModel)


class AbstractProvider(ABC):
    """Abstract Provider for configurations."""

    tags: ClassVar[
        Union[List[str], AbstractSet[str], Tuple[str, ...]]
    ]  # Pity that we can't just declare it's Iterable[str] but *not* str
    """Tags of the Provider class, used to distinguish from other providers."""

    config: ClassVar[Optional[Type[ConfigModel]]] = None
    """Config model, if the provider needs configuration (sync it with __init__'s sig)"""

    @abstractmethod
    def __init__(self, config: Optional[ConfigModel]) -> None:
        ...

    @abstractmethod
    async def fetch(self, model: Type[T_Model]) -> T_Model:
        """The actual method to generate model from provider's data."""
        ...

    @abstractmethod
    async def provided_identities(self) -> AbstractSet[str]:
        """The identities of the models that this provider supports."""
        ...

    async def apply(self, identity: str, data: Dict[str, Any]) -> None:
        """Apply the modifies from model identity."""
        raise NotImplementedError(f"{self.__class__!r} only supports `fetch`.")


_model_registry: MutableMapping[str, AbstractProvider] = WeakValueDictionary()
_provider_tag_registry: Dict[str, MutableSet[Type[AbstractProvider]]] = {}
_registered_providers: MutableSet[Type[AbstractProvider]] = WeakSet()


def add_provider_cls(cls: Type[AbstractProvider]) -> None:
    if cls in _registered_providers:
        return
    provider_tags: List[str] = list(cls.tags)
    for tag in provider_tags:
        s = _provider_tag_registry.setdefault(tag, WeakSet())
        s.add(cls)


def get_provider_cls(tags: List[str]) -> Type[AbstractProvider]:
    candidate: Set[Type[AbstractProvider]] = set(
        _provider_tag_registry.get(tags[0], set())
    )
    for tag in tags[1:]:
        candidate &= _provider_tag_registry.get(tag, set())
    if not candidate:
        raise ValueError(f"Cannot find a candidate for {tags!r}")
    if len(candidate) > 1:
        raise ValueError(f"Ambiguous candidates for {tags!r}: {candidate!r}")
    return candidate.pop()


@overload
async def add_provider(provider: AbstractProvider) -> None:
    ...


@overload
async def add_provider(
    provider: Type[AbstractProvider],
    config: Union[ConfigModel, Dict[str, Any]],
) -> None:
    ...


async def add_provider(
    provider: Union[AbstractProvider, Type[AbstractProvider]],
    config: Union[ConfigModel, Dict[str, Any], None] = None,
) -> None:
    cls = provider if isinstance(provider, type) else provider.__class__
    add_provider_cls(cls)
    if not isinstance(provider, AbstractProvider):
        if provider.config:
            provider = provider(
                provider.config(**config) if isinstance(config, dict) else config
            )
        else:
            provider = provider(None)
    for identity in await provider.provided_identities():
        if identity in _model_registry:
            raise ValueError(
                f"{identity!r} is already provided by {_model_registry[identity]}"
            )
        _model_registry[identity] = provider


class ProviderScanConfig(TypedDict):
    tags: Required[List[str]]
    configs: Required[List[Dict[str, Any]]]


async def scan_providers(configs: List[ProviderScanConfig]) -> None:
    for entry_point in entry_points(group="kayaku.providers"):
        cls: Type[AbstractProvider] = entry_point.load()
        add_provider_cls(cls)
    for config in configs:
        cls = get_provider_cls(config["tags"])
        if not cls.config:
            await add_provider(cls(None))
        for provider_config in config["configs"]:
            await add_provider(cls, provider_config)


async def create(model: Type[T_Model]) -> T_Model:
    if not model.__identity__:
        raise ValueError(
            f"{model!r} is not creatable as it doesn't have `identity` to lookup."
        )
    identity: str = model.__identity__
    if identity not in _model_registry:
        raise ValueError(f"No provider supports creating {model!r}")
    return await _model_registry[identity].fetch(model)


@dataclass
class ModifyContext:
    content: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    unsafe: bool = False


modify_context: ContextVar[ModifyContext] = ContextVar("modify_context")


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
                asyncio.create_task(_model_registry[identity].apply(identity, data))
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
