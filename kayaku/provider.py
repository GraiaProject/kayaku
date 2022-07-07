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
    Awaitable,
    ClassVar,
    Dict,
    Generator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

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

    config_cls: ClassVar[Optional[Type[ConfigModel]]] = None

    def __init__(self, config: Optional[ConfigModel]) -> None:
        self.config = config

    @staticmethod
    def available() -> bool:
        return True

    @abstractmethod
    async def load(self) -> None:
        """Reload the data entirely.
        Will always be called before `fetch`.
        """
        ...

    @abstractmethod
    async def fetch(self, model: Type[T_Model]) -> T_Model:
        """The actual method to generate model from provider's data."""
        ...

    @abstractmethod
    async def provided_identifiers(self) -> AbstractSet[str]:
        """The identifiers of the models that this provider supports."""
        ...

    async def apply(self, identifier: str, data: Dict[str, Any]) -> None:
        """Apply the modifies from model identifier."""
        raise NotImplementedError(f"{self.__class__!r} only supports `fetch`.")


class KayakuProvider(ABC):
    @abstractmethod
    def request(
        self, model: type[T_Model], flush: bool = False
    ) -> RequestTicket[T_Model]:
        ...

    @abstractmethod
    async def raw(self, domain: str) -> dict[str, Any]:
        ...

    async def fetch(self, model: type[T_Model]) -> T_Model:
        assert model.__identifier__  # TODO: Use `domain`
        return model.parse_obj(await self.raw(model.__identifier__))

    @abstractmethod
    async def domains(self) -> list[str]:
        ...

    async def has_domains(self, domain: str) -> bool:
        return domain in await self.domains()

    async def write(self, data: dict[str, Any]) -> None | RequestTicket[None]:
        raise NotImplementedError(f"{self.__class__!r} only supports read.")

    async def clear(self, model: type[ConfigModel]) -> None:
        raise NotImplemented(f"{self.__class__!r} doesn't support clear.")


_model_registry: Dict[str, AbstractProvider] = {}
_provider_tag_registry: Dict[str, Set[Type[AbstractProvider]]] = {}


def add_provider_cls(cls: Type[AbstractProvider]) -> None:
    if not cls.available():
        raise ValueError(f"{cls!r} is not available.")
    provider_tags: List[str] = list(cls.tags)
    for tag in provider_tags:
        s = _provider_tag_registry.setdefault(tag, set())
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


async def _update_provider(provider: AbstractProvider) -> None:
    global _model_registry
    _model_registry = {k: v for k, v in _model_registry.items() if v is provider}
    # pop provider-provided identifiers
    await provider.load()
    for identifier in await provider.provided_identifiers():
        if identifier in _model_registry:
            raise ValueError(
                f"{identifier!r} is already provided by {_model_registry[identifier]}"
            )
        _model_registry[identifier] = provider


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
        if provider.config_cls is not None:
            provider = provider(
                provider.config_cls(**config) if isinstance(config, dict) else config
            )
        else:
            provider = provider(None)
    await _update_provider(provider)


class ProviderScanConfig(TypedDict):
    tags: Required[List[str]]
    configs: Required[List[Dict[str, Any]]]


async def scan_providers(configs: List[ProviderScanConfig]) -> None:
    for entry_point in entry_points(group="kayaku.providers"):
        cls: Type[AbstractProvider] = entry_point.load()
        if cls.available():
            add_provider_cls(cls)
    for config in configs:
        cls = get_provider_cls(config["tags"])
        if cls.config_cls is None:
            await add_provider(cls(None))
        for provider_config in config["configs"]:
            await add_provider(cls, provider_config)


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
                [
                    asyncio.create_task(
                        _model_registry[identifier].apply(identifier, data)
                    )
                    for identifier, data in ctx.content.items()
                ]
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


T = TypeVar("T")


class RequestTicket(Awaitable[T]):
    def __init__(self, flush: bool) -> None:
        self.flush = flush
        self.fut: asyncio.Future[T] = asyncio.get_running_loop().create_future()

    @property
    def available(self) -> bool:
        return self.fut.done() and not self.fut.exception()

    def __await__(self) -> Generator[Any, None, T]:
        return self.fut.__await__()

    def unwrap(self: "RequestTicket[T]") -> T:
        if self.fut.done():
            return self.fut.result()
        raise RuntimeError("Config is not ready")
