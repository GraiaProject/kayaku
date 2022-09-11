from typing import Tuple

from pydantic import BaseConfig, BaseModel, Extra
from typing_extensions import Self


class ConfigModel(BaseModel):
    def __init_subclass__(cls, domain: str) -> None:
        domain_tup: Tuple[str, ...] = tuple(domain.split("."))
        if not all(domain_tup):
            raise ValueError(f"{domain!r} contains empty segment!")
        from .domain import _insert_domain, _Reg, domain_map

        if domain_tup in domain_map:
            raise NameError(
                f"{domain!r} is already occupied by {domain_map[domain_tup]!r}"
            )
        domain_map[domain_tup] = cls
        if _Reg._initialized:
            _insert_domain(domain_tup)
        else:
            _Reg._postponed.append(domain_tup)
        return super().__init_subclass__()

    class Config(BaseConfig):
        extra = Extra.ignore

    @classmethod
    def create(cls) -> Self:
        ...

    def save(self) -> None:
        ...
