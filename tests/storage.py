import pytest


def test_insert_spec():
    import kayaku.storage
    from kayaku.spec import PathSpec, SectionSpec, SourceSpec

    root = kayaku.storage._PrefixNode()
    empty = SectionSpec([], [])

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c"], ["d", "e", "f"], empty),
        PathSpec([".", "config"], []),
        _root=root,
    )

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c"], ["d", "e", "credential"], empty),
        PathSpec([".", "credential"], []),
        _root=root,
    )

    with pytest.raises(ValueError):
        kayaku.storage.insert(
            SourceSpec(["a", "b", "c"], ["d", "e", "credential"], empty),
            PathSpec([".", "credential"], []),
            root,
        )


def test_lookup_spec():
    import kayaku.storage
    from kayaku.spec import PathFill, PathSpec, SectionSpec, SourceSpec

    empty = SectionSpec([], [])

    root = kayaku.storage._PrefixNode()

    path_sect: list[PathFill | str] = [PathFill.EXTEND]

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c"], ["d", "e", "f"], empty),
        PathSpec([".", "config"], path_sect),
        _root=root,
    )

    kayaku.storage.insert(
        SourceSpec(
            ["a", "b", "c", "xxx"],
            [],
            empty,
        ),
        PathSpec([".", "hmm"], path_sect),
        _root=root,
    )

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c"], ["d", "e", "credential"], empty),
        PathSpec([".", "credential"], path_sect),
        _root=root,
    )

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c", "d"], ["e", "f"], empty),
        PathSpec([".", "any"], path_sect),
        _root=root,
    )

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c", "d"], ["o", "p", "e", "f"], empty),
        PathSpec([".", "whirl"], path_sect),
        _root=root,
    )

    assert (p := root.lookup(["a", "b", "c", "xxx", "d", "e", "f"])) and p[2] == (
        SourceSpec(["a", "b", "c", "xxx"], [], empty),
        PathSpec([".", "hmm"], path_sect),
    )

    assert (p := root.lookup(["a", "b", "c", "d", "e", "credential"])) and p[2] == (
        SourceSpec(["a", "b", "c"], ["d", "e", "credential"], empty),
        PathSpec([".", "credential"], path_sect),
    )

    assert (p := root.lookup(["a", "b", "c", "d", "p", "xxx", "e", "f"])) and p[2] == (
        SourceSpec(["a", "b", "c", "d"], ["e", "f"], empty),
        PathSpec([".", "any"], path_sect),
    )

    assert (p := root.lookup(["a", "b", "c", "d", "o", "p", "e", "f"])) and p[2] == (
        SourceSpec(["a", "b", "c", "d"], ["o", "p", "e", "f"], empty),
        PathSpec([".", "whirl"], path_sect),
    )

    assert root.lookup(["a", "b", "c", "d", "rand"]) is None

    assert root.lookup(["a", "b", "c", "d", "xxx", "f"]) is None
