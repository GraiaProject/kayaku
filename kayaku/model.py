import inspect
from typing import Any, Tuple, Type, TypeVar, Union, cast

from pydantic import BaseConfig, BaseModel, Extra


class ConfigModel(BaseModel):
    def __init_subclass__(cls, domain: str) -> None:
        domain_tup: Tuple[str, ...] = tuple(domain.split("."))
        if not all(domain_tup):
            raise ValueError(f"{domain!r} contains empty segment!")
        from .domain import _Reg, domain_map

        if domain_tup in domain_map:
            other = domain_map[domain_tup]
            if (
                cls.__module__ == other.__module__
                and cls.__qualname__ == other.__qualname__
            ):
                if inspect.signature(cls) == inspect.signature(other):
                    return
                else:
                    # TODO: log warning
                    ...
            raise NameError(
                f"{domain!r} is already occupied by {domain_map[domain_tup]!r}"
            )
        domain_map[domain_tup] = cls
        if _Reg.initialized:
            raise RuntimeError(
                f"kayaku is already fully initialized, adding {cls} is not allowed."
            )
        else:
            _Reg.postponed.append(domain_tup)
        return super().__init_subclass__()

    class Config(BaseConfig):
        extra = Extra.ignore
        validate_assignment: bool = True


T_Model = TypeVar("T_Model", bound=ConfigModel)


def create(cls: Type[T_Model]) -> T_Model:
    from .domain import _Reg

    return cast(T_Model, _Reg.model_map[cls])


def save(model: Union[T_Model, Type[T_Model]]) -> None:
    from .backend.api import json5
    from .domain import _Reg

    inst: ConfigModel = _Reg.model_map[model] if isinstance(model, type) else model
    fmt_path = _Reg.model_path[inst.__class__]
    fmt_path.path.write_text(json5.dumps(inst.dict(by_alias=True)), "utf-8")
