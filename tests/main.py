import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from kayaku.model import ConfigModel


@contextmanager
def kayaku_test_ctx() -> Generator[Path, None, None]:
    import kayaku.domain
    from kayaku.domain import _Registry, domain_map, file_map

    kayaku.domain._reg = _Registry()
    domain_map.clear()
    file_map.clear()

    with tempfile.TemporaryDirectory() as pth:
        yield Path(pth).resolve()


def ph1():
    class ModelA(ConfigModel, domain="a.b.c"):
        val: int

    with kayaku_test_ctx() as pth:
        ...  # TODO


def test_all():
    ph1()
