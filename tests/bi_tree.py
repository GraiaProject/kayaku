import shutil
from pathlib import Path

import pytest

base_pth = Path("./temp/storage/").resolve()
if base_pth.exists():
    shutil.rmtree(base_pth.as_posix())
base_pth.mkdir(parents=True, exist_ok=True)


def insert_spec(root, src, path) -> None:
    prefix, suffix = src.prefix, src.suffix
    target_nd = root.insert(prefix).insert(reversed(suffix))
    if target_nd.bound:
        raise ValueError(
            f"{'.'.join(prefix + ['*'] + suffix)} is already bound to {target_nd.bound}"
        )
    target_nd.bound = (src, path)


def test_insert_spec():
    import kayaku.bi_tree
    from kayaku.spec import PathSpec, SectionSpec, SourceSpec

    root = kayaku.bi_tree.Prefix()
    empty = SectionSpec([], [])

    insert_spec(
        root,
        SourceSpec(["a", "b", "c"], ["d", "e", "f"], empty),
        PathSpec([*base_pth.parts, "config"], []),
    )

    insert_spec(
        root,
        SourceSpec(["a", "b", "c"], ["d", "e", "credential"], empty),
        PathSpec([*base_pth.parts, "credential"], []),
    )

    with pytest.raises(ValueError):
        insert_spec(
            root,
            SourceSpec(["a", "b", "c"], ["d", "e", "credential"], empty),
            PathSpec([*base_pth.parts, "credential"], []),
        )


def test_lookup_spec():
    import kayaku.bi_tree
    import kayaku.spec
    from kayaku.spec import PathFill, PathSpec, SectionSpec, SourceSpec

    empty = SectionSpec([], [])

    root = kayaku.bi_tree.Prefix()
    path_sect = [PathFill.EXTEND]

    insert_spec(
        root,
        SourceSpec(["a", "b", "c"], ["d", "e", "f"], empty),
        PathSpec([*base_pth.parts, "config"], path_sect),
    )

    insert_spec(
        root,
        SourceSpec(
            ["a", "b", "c", "xxx"],
            [],
            empty,
        ),
        PathSpec([*base_pth.parts, "hmm"], path_sect),
    )

    insert_spec(
        root,
        SourceSpec(["a", "b", "c"], ["d", "e", "credential"], empty),
        PathSpec([*base_pth.parts, "credential"], path_sect),
    )

    insert_spec(
        root,
        SourceSpec(["a", "b", "c", "d"], ["e", "f"], empty),
        PathSpec([*base_pth.parts, "any"], path_sect),
    )

    insert_spec(
        root,
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
    import kayaku.bi_tree
    from kayaku.spec import DestWithMount, parse_path, parse_source

    root = kayaku.bi_tree.Prefix()
    insert_spec(
        root,
        parse_source("a.b.c.{**}"),
        parse_path(base_pth.as_posix() + "/a/b/c::{}"),
    )

    insert_spec(
        root,
        parse_source("a.b.{**}"),
        parse_path(base_pth.as_posix() + "/d/e/f::{**}"),
    )

    assert (p := root.lookup(["a", "b", "c", "d", "e"])) and p[1] == DestWithMount(
        Path(base_pth, "d/e/f").as_posix(), ("c", "d", "e")
    )


def test_spec_lookup_wrapped():
    import kayaku.bi_tree
    from kayaku.spec import DestWithMount, parse_path, parse_source

    root = kayaku.bi_tree.Prefix()
    insert_spec(
        root,
        parse_source("a.b.c.{**}"),
        parse_path(base_pth.as_posix() + "/a/b/c::{}"),
    )
    assert root.lookup(["a", "b", "c", "d", "e"]) is None

    insert_spec(
        root,
        parse_source("a.b.{**}"),
        parse_path(base_pth.as_posix() + "/d/e/f.jsonc::{**}"),
    )

    assert root.lookup(["a", "b", "c", "d", "e"])[1] == DestWithMount(
        Path(base_pth, "d/e/f.jsonc").as_posix(), ("c", "d", "e")
    )
