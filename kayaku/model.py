from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Literal, Optional, Type
from weakref import WeakValueDictionary as WeakVDict

from pydantic import BaseModel
from typing_extensions import Self

_domain_map: "WeakVDict[str, Type[ConfigModel]]" = WeakVDict()

ModifyPolicy = Literal["allow", "protected", "readonly"]

_get_attr_parts: List[str] = []


class ConfigModel(BaseModel):
    __domain__: ClassVar[Optional[str]]
    __policy__: ClassVar[ModifyPolicy]

    def __init_subclass__(
        cls, *, domain: Optional[str] = None, policy: ModifyPolicy = "allow"
    ) -> None:
        cls.__domain__ = domain
        if domain:
            if domain in _domain_map:
                raise ValueError(
                    f"domain {domain!r} is already registered by {_domain_map[domain]!r}"
                )
            _domain_map[domain] = cls
        cls.__policy__ = policy
        # assert not nested inside other config
        for field in cls.__fields__.values():
            f_type = field.type_
            if (
                isinstance(f_type, type)
                and issubclass(f_type, ConfigModel)
                and f_type.__domain__
            ):
                raise ValueError(
                    f"{f_type!r} defined domain {f_type.__domain__!r}, "
                    "which is not allowed in nested ConfigModel."
                )

    @classmethod
    async def create(cls, flush: bool = False) -> Self:
        from kayaku.provider import model_registry, providers

        if not cls.__domain__:
            raise ValueError(
                f"{cls!r} is not creatable as it doesn't have `domain` to lookup."
            )
        domain: str = cls.__domain__
        if domain in model_registry:
            provider = model_registry[domain]
        else:
            for provider in providers:
                if await provider.has_domains(domain):
                    break
            else:
                raise ValueError(f"No provider found for domain {domain!r}")
        return await provider.request(cls, flush=flush)

    async def apply_modifies(self) -> None:
        from kayaku.provider import model_registry, modify_context

        ctx = modify_context.get()
        if self.__domain__ not in ctx.content:
            return
        content = ctx.content[self.__domain__]
        await model_registry[self.__domain__].write(self.__domain__, content)

    def __setattr__(self, name: str, value: Any):
        from kayaku.provider import modify_context

        try:
            ctx = modify_context.get()
        except LookupError as e:
            raise LookupError("Use `with kayaku.modify()` for modification") from e
        if self.__policy__ == "readonly":
            raise RuntimeError(f"You can't setattr on readonly model {self!r}")
        elif self.__policy__ == "protected" and not ctx.unsafe:
            raise RuntimeError(f"You can't setattr on protected model {self!r}")
        content: Dict[str, Any] = ctx.content
        for access_key in _get_attr_parts:
            content = content.setdefault(access_key, {})
        content[name] = value
        _get_attr_parts.clear()
        return super().__setattr__(name, value)

    if not TYPE_CHECKING:  # avoid being recognized as fallback

        def __getattribute__(self, __name: str):
            from kayaku.provider import modify_context

            get = super().__getattribute__
            if (
                modify_context.get(None) is None
            ):  # a fast route, don't save when not in modify ctx
                return get(__name)
            if type(self).__domain__:
                _get_attr_parts.clear()
                _get_attr_parts.append(type(self).__domain__)
            if __name in type(self).__fields__:
                _get_attr_parts.append(__name)
            return get(__name)
