import asyncio
from pathlib import Path

from kayaku import ConfigModel, modify
from kayaku.providers.toml import TOMLConfig, TOMLReadWriteProvider


class Project(ConfigModel, domain="project"):
    name: str
    authors: list
    urls: dict

    class Config:
        extra = "allow"


async def main():
    TOMLReadWriteProvider(TOMLConfig(path=Path("./tmp.toml")))
    p = await Project.create()
    print(p)
    async with modify():
        p.name = "playground"
        p.authors.append({"name": "GraiaCommunity", "email": "governance@graiax.cn"})
    print(p)


asyncio.run(main())
