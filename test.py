import asyncio

from kayaku import ConfigModel, modify


class Project(ConfigModel, domain="project"):
    name: str
    authors: list
    urls: dict

    class Config:
        extra = "allow"


async def main():
    p = await Project.create()
    print(p)
    async with modify():
        p.name = "playground"
        p.authors.append({"name": "GraiaCommunity", "email": "governance@graiax.cn"})
    print(p)


asyncio.run(main())
