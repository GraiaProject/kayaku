from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Dict, Type, TypeVar

if TYPE_CHECKING:
    from kayaku.model import ConfigModel

    T_Model = TypeVar("T_Model", bound=ConfigModel)

modify_context: ContextVar[Dict[str, dict]] = ContextVar("modify_context")


class BaseProvider:
    def fetch(self, model: Type[T_Model]) -> T_Model:
        ...

    async def apply_modifies(self):
        raise NotImplementedError(f"{self.__class__!r} only supports `fetch`.")
