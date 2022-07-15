from __future__ import annotations

import asyncio
import functools
from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
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
from typing_extensions import Required, Self, TypedDict

if TYPE_CHECKING:
    from kayaku.model import ConfigModel

    T_Model = TypeVar("T_Model", bound=ConfigModel)

providers: Set[KayakuProvider] = set()


class KayakuProvider(ABC):
    tags: ClassVar[Dict[str, int]]
    config_model: ClassVar[Type[ConfigModel]]

    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls)
        providers.add(obj)
        return obj

    @abstractmethod
    def request(
        self, model: type[T_Model], flush: bool = False
    ) -> RequestTicket[T_Model]:
        ...

    @abstractmethod
    async def raw(self, domain: str) -> dict[str, Any]:
        ...

    async def fetch(self, model: type[T_Model]) -> T_Model:
        assert model.__domain__
        return model.parse_obj(await self.raw(model.__domain__))

    @abstractmethod
    async def domains(self) -> list[str]:
        ...

    @classmethod
    @abstractmethod
    def construct(cls, config: ConfigModel) -> Self:
        ...

    @staticmethod
    def available() -> bool:
        return True

    async def has_domains(self, domain: str) -> bool:
        return domain in await self.domains()

    async def write(self, domain: str, data: dict[str, Any]) -> None:
        raise NotImplementedError(f"{self.__class__!r} only supports read.")

    @staticmethod
    def wrap_request(*, cache: bool):
        def wrapper(
            func: Callable[[T, type[T_Model], bool], RequestTicket[T_Model]]
        ) -> Callable[[T, type[T_Model], bool], RequestTicket[T_Model]]:
            @functools.wraps(func)
            def inner(self: T, model: type[T_Model], flush: bool = False):
                if not model.__domain__:
                    raise ValueError(f"{model!r} doesn't have domain!")
                if model.__domain__ in _model_cache:
                    if not flush:
                        ticket = RequestTicket(flush)
                        ticket.fut.set_result(_model_cache[model.__domain__])
                        return ticket
                    del _model_cache[model.__domain__]
                ticket = func(self, model, flush)
                if cache:
                    _model_cache[model.__domain__] = ticket.fut.result()
                return ticket

            return inner

        return wrapper


model_registry: Dict[str, KayakuProvider] = {}
_model_cache: Dict[str, ConfigModel] = {}


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
                    asyncio.create_task(model_registry[domain].write(domain, data))
                    for domain, data in ctx.content.items()
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
