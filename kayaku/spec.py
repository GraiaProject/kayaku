from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import Literal


@dataclass
class BaseSpec:
    prefix: list[str]
    tag: str | None


@dataclass
class PatternSpec(BaseSpec):
    section: BaseSpec


@dataclass
class PathSpec:
    path: list[str]
    file_parts: int
    section_suffix: list[str]


def clear_buf(buf: list[str]) -> str:
    res: str = "".join(buf)
    buf.clear()
    return res


class Pattern:
    def __init__(self, spec: str):
        self.spec: str = spec
        self.quote: Literal[None, '"', "'"] = None
        self.tag_flag: bool = False
        self.section_flag: Literal[None, True, False] = None
        self.sect: BaseSpec = BaseSpec([], None)
        self.res: PatternSpec = PatternSpec([], None, self.sect)
        self.buf: list[str] = []

    def parse_sep(self, index: int):
        if not self.buf:
            raise ValueError(f"Found empty specifier at {index}")
        if self.res.tag is not None:
            raise ValueError(f"Dot separator found after tag specifier at {index}")
        if self.tag_flag:
            self.res.tag = clear_buf(self.buf)
            if self.section_flag:
                self.sect.tag = self.res.tag
        else:
            self.res.prefix.append(clear_buf(self.buf))
            if self.section_flag:
                self.sect.prefix.append(self.res.prefix[-1])

    def parse_tag_symbol(self, index: int):
        if self.tag_flag:
            raise ValueError(f"Duplicated tag symbol (:) found at {index}")
        self.parse_sep(index)
        self.tag_flag = True

    def parse_r_bracket(self, it: "enumerate[str]", index: int):
        if self.section_flag is True:
            with suppress(StopIteration):
                index, char = next(it)
                if char not in (".", ":"):
                    raise ValueError(
                        f"Found right bracket not followed by separator at {index}"
                    )
                if char == ":":
                    self.parse_tag_symbol(index)
                    self.section_flag = False
                    return
            self.parse_sep(index)
            self.section_flag = False
        elif self.section_flag is False:
            raise ValueError(f"Duplicated right curly bracket found at {index}")
        else:
            raise ValueError(f"Unmatched right curly bracket found at {index}")

    def parse(self) -> PatternSpec:
        it: "enumerate[str]" = enumerate(self.spec)
        for index, char in it:
            if self.quote is None:
                if char == ".":
                    self.parse_sep(index)
                elif char == "{":
                    if self.buf:
                        raise ValueError(
                            f"Found left bracket not following separator at {index}"
                        )
                    if self.section_flag is None:
                        self.section_flag = True
                    else:
                        raise ValueError(f"Duplicated left bracket found at {index}")
                elif char == "}":
                    self.parse_r_bracket(it, index)
                elif char == ":":
                    self.parse_tag_symbol(index)
                elif char in ('"', "'"):
                    self.quote = char
                else:
                    self.buf.append(char)
            elif self.quote == char:
                self.quote = None
            else:
                self.buf.append(char)
        if self.buf:
            self.parse_sep(len(self.spec))
        if self.res.prefix and self.res.prefix[-1] == "*":
            self.res.prefix.pop()
        if self.sect.prefix and self.sect.prefix[-1] == "*":
            self.sect.prefix.pop()
        return self.res
