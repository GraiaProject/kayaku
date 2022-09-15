from typing import Any, Tuple, Type, TypeVar, Union, cast

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
    import tomlkit

    from .domain import _model_map, _model_path
    from .toml_utils import validate_data
    from .toml_utils.modify import update_from_model

    inst: ConfigModel = _model_map[model] if isinstance(model, type) else model
    fmt_path = _model_path[inst.__class__]
    document = tomlkit.loads(fmt_path.path.read_text("utf-8"))
    container: Any = document
    for sect in fmt_path.section:
        container = container[sect]
    data = inst.dict(by_alias=True, exclude_none=True)
    validate_data(data)
    update_from_model(container, data)
    fmt_path.path.write_text(tomlkit.dumps(document), "utf-8")
