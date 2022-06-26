from kayaku.model import ConfigModel
from kayaku.provider import modify, modify_context


class C(ConfigModel, policy="protected"):
    v: int


class M(ConfigModel, identity="m"):
    c: C


m = M(c=C(v=5))

with modify():
    m.c.v = 4
    print(modify_context.get())
# RuntimeError is fine, as there's no Provider
