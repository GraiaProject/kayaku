from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import cast

from typing_extensions import TypedDict

_LIG = r"[A-Za-z0-9_-]"
_L_REP = rf"({_LIG}+\.)*"
_R_REP = rf"(\.{_LIG}+)*"
SOURCE_REGEX = re.compile(
    rf"(?P<prefix>{_L_REP}){{(?P<sect_prefix>{_L_REP})\*\*(?P<sect_suffix>{_R_REP})}}(?P<suffix>{_R_REP})"
)


@dataclass
class SectionSpec:
    prefix: list[str]
    suffix: list[str]


@dataclass
class SourceSpec:
    prefix: list[str]
    suffix: list[str]
    section: SectionSpec


class SourceRegexGroup(TypedDict):
    prefix: str
    sect_prefix: str
    sect_suffix: str
    suffix: str


def parse_source(spec: str) -> SourceSpec:
    if not (match_res := SOURCE_REGEX.fullmatch(spec)):
        raise ValueError(f"{spec!r} doesn't match {SOURCE_REGEX.pattern!r}")
    groups: SourceRegexGroup = cast(SourceRegexGroup, match_res.groupdict())
    section: SectionSpec = SectionSpec(
        groups["sect_prefix"].split(".")[:-1], groups["sect_suffix"].split(".")[1:]
    )
    return SourceSpec(
        groups["prefix"].split(".")[:-1] + section.prefix,
        section.suffix + groups["suffix"].split(".")[1:],
        section,
    )


class PathFill(enum.Enum):
    SINGLE = object()  # {} or {*}
    EXTEND = object()  # {**}


@dataclass
class PathSpec:
    path: list[str | PathFill]
    section: list[str | PathFill]


def parse_path(spec: str) -> PathSpec:
    replacer = {"{*}": PathFill.SINGLE, "{}": PathFill.SINGLE, "{**}": PathFill.EXTEND}
    location, section = spec.split(":", 1)
    if ":" in section:
        raise ValueError(f"Spec {spec!r} contains multiple ':'")
    path_parts: list[str | PathFill] = [replacer.get(l, l) for l in location.split("/")]
    section_parts: list[str | PathFill] = [
        replacer.get(l, l) for l in section.split(".")
    ]
    if path_parts.count(PathFill.EXTEND) + section_parts.count(PathFill.EXTEND) > 1:
        raise ValueError(f"""Found more than one "extend" part ({{**}}) in {spec}""")
    return PathSpec(path_parts, section_parts)
