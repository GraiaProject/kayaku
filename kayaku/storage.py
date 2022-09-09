from __future__ import annotations

from .spec import PathSpec

# TODO: lookup impl


class _SuffixNode:
    bound: PathSpec | None

    def __init__(self) -> None:
        self.bound = None
        self.nxt: dict[str, _SuffixNode] = {}

    def insert(self, frags: list[str], index: int = 0) -> _SuffixNode:
        if index == len(frags):
            return self
        nxt = self.nxt.setdefault(frags[index], _SuffixNode())
        return nxt.insert(frags, index + 1)


class _PrefixNode:
    suffix: _SuffixNode | None

    def __init__(self) -> None:
        self.suffix = None
        self.nxt: dict[str, _PrefixNode] = {}

    def insert(self, frags: list[str], index: int = 0) -> _SuffixNode:
        if index == len(frags):
            if not self.suffix:
                self.suffix = _SuffixNode()
            return self.suffix
        nxt = self.nxt.setdefault(frags[index], _PrefixNode())
        return nxt.insert(frags, index + 1)


_root = _PrefixNode()


def insert(prefix: list[str], suffix: list[str], path: PathSpec):
    suffix_nd = _root.insert(prefix)
    target_nd = suffix_nd.insert(suffix)
    if target_nd.bound:
        raise ValueError(
            f"{'.'.join(prefix + ['*'] + suffix)} is already bound to {target_nd.bound}"
        )
    target_nd.bound = path
