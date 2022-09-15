from typing import Tuple, Type, TypeVar, Union, cast

from pydantic import BaseConfig, BaseModel, Extra


class ConfigModel(BaseModel):
    def __init_subclass__(cls, domain: str) -> None:
        domain_tup: Tuple[str, ...] = tuple(domain.split("."))
        if not all(domain_tup):
            raise ValueError(f"{domain!r} contains empty segment!")
        from .domain import _Reg, domain_map

        if domain_tup in domain_map:
            raise NameError(
                f"{domain!r} is already occupied by {domain_map[domain_tup]!r}"
            )
        domain_map[domain_tup] = cls
        if _Reg._initialized:
            raise RuntimeError(
                f"kayaku is already fully initialized, adding {cls} is not allowed."
            )
        else:
            _Reg._postponed.append(domain_tup)
        return super().__init_subclass__()

    class Config(BaseConfig):
        extra = Extra.ignore
        validate_assignment: bool = True


T_Model = TypeVar("T_Model", bound=ConfigModel)


def create(cls: Type[T_Model]) -> T_Model:
    from .domain import _model_map

    return cast(T_Model, _model_map[cls])


def save(model: Union[T_Model, Type[T_Model]]) -> None:
    from .domain import _model_map

    inst: ConfigModel = _model_map[model] if isinstance(model, type) else model

    return
