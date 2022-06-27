import asyncio

from kayaku import ConfigModel, scan_providers
from kayaku.provider import ProviderScanConfig


class Project(ConfigModel, identifier="project"):
    class Config:
        extra = "allow"


async def main():
    await scan_providers(
        [
            ProviderScanConfig(
                tags=["toml"],
                configs=[
                    {"path": "./pyproject.toml", "filtering": (True, ["project"])}
                ],
            )
        ]
    )
    print(await Project.create())


asyncio.run(main())
