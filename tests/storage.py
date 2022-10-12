import shutil
from pathlib import Path

import pytest

base_pth = Path("./temp/storage/").resolve()
if base_pth.exists():
    shutil.rmtree(base_pth.as_posix())
base_pth.mkdir(parents=True, exist_ok=True)


def test_insert_spec():
    import kayaku.storage
    from kayaku.spec import PathSpec, SectionSpec, SourceSpec

    root = kayaku.storage._PrefixNode()
    kayaku.storage._root.set(root)
    empty = SectionSpec([], [])

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c"], ["d", "e", "f"], empty),
        PathSpec([*base_pth.parts, "config"], []),
    )

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c"], ["d", "e", "credential"], empty),
        PathSpec([*base_pth.parts, "credential"], []),
    )

    with pytest.raises(ValueError):
        kayaku.storage.insert(
            SourceSpec(["a", "b", "c"], ["d", "e", "credential"], empty),
            PathSpec([*base_pth.parts, "credential"], []),
        )


def test_lookup_spec():
    import kayaku.spec
    import kayaku.storage
    from kayaku.spec import PathFill, PathSpec, SectionSpec, SourceSpec

    empty = SectionSpec([], [])

    root = kayaku.storage._PrefixNode()
    kayaku.storage._root.set(root)
    path_sect = [PathFill.EXTEND]

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c"], ["d", "e", "f"], empty),
        PathSpec([*base_pth.parts, "config"], path_sect),
    )

    kayaku.storage.insert(
        SourceSpec(
            ["a", "b", "c", "xxx"],
            [],
            empty,
        ),
        PathSpec([*base_pth.parts, "hmm"], path_sect),
    )

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c"], ["d", "e", "credential"], empty),
        PathSpec([*base_pth.parts, "credential"], path_sect),
    )

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c", "d"], ["e", "f"], empty),
        PathSpec([*base_pth.parts, "any"], path_sect),
    )

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c", "d"], ["o", "p", "e", "f"], empty),
        PathSpec([*base_pth.parts, "whirl"], path_sect),
    )

    assert (p := root.lookup(["a", "b", "c", "xxx", "d", "e", "f"])) and p[0] == (
        SourceSpec(["a", "b", "c", "xxx"], [], empty),
        PathSpec([*base_pth.parts, "hmm"], path_sect),
    )

    assert (p := root.lookup(["a", "b", "c", "d", "e", "credential"])) and p[0] == (
        SourceSpec(["a", "b", "c"], ["d", "e", "credential"], empty),
        PathSpec([*base_pth.parts, "credential"], path_sect),
    )

    assert (p := root.lookup(["a", "b", "c", "d", "p", "xxx", "e", "f"])) and p[0] == (
        SourceSpec(["a", "b", "c", "d"], ["e", "f"], empty),
        PathSpec([*base_pth.parts, "any"], path_sect),
    )

    assert (p := root.lookup(["a", "b", "c", "d", "o", "p", "e", "f"])) and p[0] == (
        SourceSpec(["a", "b", "c", "d"], ["o", "p", "e", "f"], empty),
        PathSpec([*base_pth.parts, "whirl"], path_sect),
    )

    assert root.lookup(["a", "b", "c", "d", "rand"]) is None

    assert root.lookup(["a", "b", "c", "d", "xxx", "f"]) is None


def test_spec_lookup_fmt_err():
    import kayaku.storage
    from kayaku.spec import FormattedPath, parse_path, parse_source

    root = kayaku.storage._PrefixNode()
    kayaku.storage._root.set(root)
    kayaku.storage.insert(
        parse_source("a.b.c.{**}"),
        parse_path(base_pth.as_posix() + "/a/b/c::{}"),
    )

    kayaku.storage.insert(
        parse_source("a.b.{**}"),
        parse_path(base_pth.as_posix() + "/d/e/f::{**}"),
    )

    assert (p := root.lookup(["a", "b", "c", "d", "e"])) and p[1] == FormattedPath(
        Path(base_pth, "d/e/f"), ["c", "d", "e"]
    )


def test_spec_lookup_wrapped():
    import kayaku.storage
    from kayaku.spec import FormattedPath, parse_path, parse_source

    root = kayaku.storage._PrefixNode()
    kayaku.storage._root.set(root)
    kayaku.storage.insert(
        parse_source("a.b.c.{**}"),
        parse_path(base_pth.as_posix() + "/a/b/c::{}"),
    )
    with pytest.raises(ValueError):
        kayaku.storage.lookup(["a", "b", "c", "d", "e"])

    kayaku.storage.insert(
        parse_source("a.b.{**}"),
        parse_path(base_pth.as_posix() + "/d/e/f.jsonc::{**}"),
    )

    assert kayaku.storage.lookup(["a", "b", "c", "d", "e"]) == FormattedPath(
        Path(base_pth, "d/e/f.jsonc"), ["c", "d", "e"]
    )
