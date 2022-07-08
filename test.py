import asyncio

from kayaku import ConfigModel, modify, scan_providers
from kayaku.provider import ProviderScanConfig


class Project(ConfigModel, domain="project"):
    name: str
    authors: list
    urls: dict

    class Config:
        extra = "allow"


async def main():
    await scan_providers(
        [
            ProviderScanConfig(
                tags=["toml", "write"],
                configs=[
                    {"path": "./playground.toml", "filtering": (True, ["project"])}
                ],
            )
        ]
    )
    p = await Project.create()
    print(p)
    async with modify():
        p.name = "playground"
        p.authors.append({"name": "GraiaCommunity", "email": "governance@graiax.cn"})
    print(p)


asyncio.run(main())
