from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Literal, Optional, Type
from weakref import WeakValueDictionary as WeakVDict

from pydantic import BaseConfig, BaseModel

_identified_models: "WeakVDict[str, Type[ConfigModel]]" = WeakVDict()

ModifyPolicy = Literal["allow", "protected", "readonly"]

_last_access: List[str] = []


class ConfigModel(BaseModel):
    __identity__: ClassVar[Optional[str]]
    __policy__: ClassVar[ModifyPolicy]

    class Config(BaseConfig):
        validate_assignment = True

    def __init_subclass__(
        cls, *, identity: Optional[str] = None, policy: ModifyPolicy = "allow"
    ) -> None:
        cls.__identity__ = identity
        if identity:
            if identity in _identified_models:
                raise ValueError(
                    f"Identity {identity!r} is already registered by {_identified_models[identity]!r}"
                )
            _identified_models[identity] = cls
        cls.__policy__ = policy
        # assert not nested inside other config
        for field in cls.__fields__.values():
            if issubclass(field.type_, ConfigModel) and field.type_.__identity__:
                raise ValueError(
                    f"{field.type_!r} defined identity {field.type_.__identity__!r}, "
                    "which is not allowed in nested ConfigModel."
                )

    if not TYPE_CHECKING:

        def __getattribute__(self, __name: str):
            from kayaku.provider import modify_context

            get = super().__getattribute__
            if modify_context.get(None) is None:
                return get(__name)
            if type(self).__identity__:
                _last_access.clear()
                _last_access.append(type(self).__identity__)
            if __name in type(self).__fields__:
                _last_access.append(__name)
            return get(__name)

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
            for access_key in _last_access:
                content = content.setdefault(access_key, {})
            content[name] = value
            _last_access.clear()
            ctx.synced = False
            return super().__setattr__(name, value)
