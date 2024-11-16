from __future__ import annotations

from collections.abc import Iterable, Sequence

from .spec import DestWithMount, PathSpec, SourceSpec


class Suffix:
    bound: tuple[SourceSpec, PathSpec] | None

    def __init__(self) -> None:
        self.bound = None
        self.nxt: dict[str, Suffix] = {}

    def insert(self, frags: Iterable[str]) -> Suffix:
        node = self
        for frag in frags:
            node = node.nxt.setdefault(frag, Suffix())
        return node

    def lookup(
        self, frags: Iterable[str]
    ) -> tuple[int, tuple[SourceSpec, PathSpec] | None]:
        node = self
        bound = self.bound
        last_index = 0
        for index, frag in enumerate(frags):
            if nxt_nd := node.nxt.get(frag, None):
                node = nxt_nd
                if node.bound:
                    bound = node.bound
                    last_index = index
        return last_index, bound


class Prefix:
    suffix: Suffix | None

    def __init__(self) -> None:
        self.suffix = None
        self.nxt: dict[str, Prefix] = {}

    def insert(self, frags: Iterable[str]) -> Suffix:
        node = self
        for frag in frags:
            node = node.nxt.setdefault(frag, Prefix())
        if not node.suffix:
            node.suffix = Suffix()
        return node.suffix

    def lookup(
        self, frags: Sequence[str], index: int = 0
    ) -> tuple[tuple[SourceSpec, PathSpec], DestWithMount] | None:
        if index < len(frags) and (nxt_nd := self.nxt.get(frags[index], None)):
            if lookup_res := nxt_nd.lookup(frags, index + 1):
                return lookup_res
        if self.suffix:
            suffix_ind, spec = self.suffix.lookup(reversed(frags[index:]))
            if spec:
                src_spec, path_spec = spec
                parts = (
                    src_spec.section.prefix
                    + list(frags[index : -suffix_ind or None])
                    + src_spec.section.suffix
                )
                if formatted := path_spec.format(parts):
                    return spec, formatted
