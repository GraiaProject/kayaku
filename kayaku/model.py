from typing import Tuple

from pydantic import BaseConfig, BaseModel, Extra


class ConfigModel(BaseModel):
    def __init_subclass__(cls, domain: str) -> None:
        domain_tup: Tuple[str, ...] = tuple(domain.split("."))
        if not all(domain_tup):
            raise ValueError(f"{domain!r} contains empty segment!")
        from .domain import DomainRegistry, _insert_domain

        if domain_tup in DomainRegistry.domain_map:
            raise NameError(
                f"{domain!r} is already occupied by {DomainRegistry.domain_map[domain_tup]!r}"
            )
        DomainRegistry.domain_map[domain_tup] = cls
        if DomainRegistry._initialized:
            _insert_domain(domain_tup)
        else:
            DomainRegistry._postponed.append(domain_tup)
        return super().__init_subclass__()

    class Config(BaseConfig):
        extra = Extra.ignore
