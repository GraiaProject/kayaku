from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Literal, Optional, Type
from weakref import WeakValueDictionary as WeakVDict

from pydantic import BaseConfig, BaseModel
from typing_extensions import Self

_identified_models: "WeakVDict[str, Type[ConfigModel]]" = WeakVDict()

ModifyPolicy = Literal["allow", "protected", "readonly"]

_get_attr_parts: List[str] = []


class ConfigModel(BaseModel):
    __identifier__: ClassVar[Optional[str]]
    __policy__: ClassVar[ModifyPolicy]

    def __init_subclass__(
        cls, *, identifier: Optional[str] = None, policy: ModifyPolicy = "allow"
    ) -> None:
        cls.__identifier__ = identifier
        if identifier:
            if identifier in _identified_models:
                raise ValueError(
                    f"identifier {identifier!r} is already registered by {_identified_models[identifier]!r}"
                )
            _identified_models[identifier] = cls
        cls.__policy__ = policy
        # assert not nested inside other config
        for field in cls.__fields__.values():
            f_type = field.type_
            if (
                isinstance(f_type, type)
                and issubclass(f_type, ConfigModel)
                and f_type.__identifier__
            ):
                raise ValueError(
                    f"{f_type!r} defined identifier {f_type.__identifier__!r}, "
                    "which is not allowed in nested ConfigModel."
                )

    async def apply_modifies(self) -> None:
        from kayaku.provider import _model_registry, modify_context

        ctx = modify_context.get()
        if self.__identifier__ not in ctx.content:
            return
        content = ctx.content[self.__identifier__]
        await _model_registry[self.__identifier__].apply(self.__identifier__, content)

    async def reload(self) -> None:
        from kayaku.provider import _model_registry

        if not self.__identifier__:
            raise NameError(f"{self} doesn't have identifier!")
        provider = _model_registry[self.__identifier__]
        await provider.load()  # reload data
        self.__dict__.update((await provider.fetch(self.__class__)).__dict__)

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

    @classmethod
    async def create(cls, reload: bool = False) -> Self:
        from kayaku.provider import _model_registry

        if not cls.__identifier__:
            raise ValueError(
                f"{cls!r} is not creatable as it doesn't have `identifier` to lookup."
            )
        identifier: str = cls.__identifier__
        if identifier not in _model_registry:
            raise ValueError(f"No provider supports creating {cls!r}")
        provider = _model_registry[identifier]
        if reload:
            await provider.load()
        return await provider.fetch(cls)

    if not TYPE_CHECKING:  # avoid being recognized as fallback

        def __getattribute__(self, __name: str):
            from kayaku.provider import modify_context

            get = super().__getattribute__
            if (
                modify_context.get(None) is None
            ):  # a fast route, don't save when not in modify ctx
                return get(__name)
            if type(self).__identifier__:
                _get_attr_parts.clear()
                _get_attr_parts.append(type(self).__identifier__)
            if __name in type(self).__fields__:
                _get_attr_parts.append(__name)
            return get(__name)
