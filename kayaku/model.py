from typing import ClassVar, Optional, Type
from weakref import WeakValueDictionary as WeakVDict

from pydantic import BaseConfig, BaseModel

_identified_models: "WeakVDict[str, Type[ConfigModel]]" = WeakVDict()


class ConfigModel(BaseModel):
    __identity__: ClassVar[Optional[str]]
    __protected__: ClassVar[bool]

    class Config(BaseConfig):
        validate_assignment = True

    def __init_subclass__(
        cls, *, identity: Optional[str] = None, protected: bool = False
    ) -> None:
        cls.__identity__ = identity
        if identity:
            if identity in _identified_models:
                raise ValueError(
                    f"Identity {identity!r} is already registered by {_identified_models[identity]!r}"
                )
            _identified_models[identity] = cls
        cls.__protected__ = protected
        # assert not nested inside other config
        for field in cls.__fields__.values():
            if issubclass(field.type_, ConfigModel) and field.type_.__identity__:
                raise ValueError(
                    f"{field.type_!r} defined identity {field.type_.__identity__!r}, "
                    "which is not allowed in nested ConfigModel."
                )
