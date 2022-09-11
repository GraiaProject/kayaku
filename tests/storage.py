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
    from kayaku.spec import PathSpec, SectionSpec, SourceSpec

    empty = SectionSpec([], [])

    root = kayaku.storage._PrefixNode()

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c"], ["d", "e", "f"], empty),
        PathSpec([".", "config"], []),
        _root=root,
    )

    kayaku.storage.insert(
        SourceSpec(
            ["a", "b", "c", "xxx"],
            [],
            empty,
        ),
        PathSpec([".", "hmm"], []),
        _root=root,
    )

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c"], ["d", "e", "credential"], empty),
        PathSpec([".", "credential"], []),
        _root=root,
    )

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c", "d"], ["e", "f"], empty),
        PathSpec([".", "any"], []),
        _root=root,
    )

    kayaku.storage.insert(
        SourceSpec(["a", "b", "c", "d"], ["o", "p", "e", "f"], empty),
        PathSpec([".", "whirl"], []),
        _root=root,
    )

    assert (p := root.lookup(["a", "b", "c", "xxx", "d", "e", "f"])) and p[2] == (
        SourceSpec(["a", "b", "c", "xxx"], [], empty),
        PathSpec([".", "hmm"], []),
    )

    assert (p := root.lookup(["a", "b", "c", "d", "e", "credential"])) and p[2] == (
        SourceSpec(["a", "b", "c"], ["d", "e", "credential"], empty),
        PathSpec([".", "credential"], []),
    )

    assert (p := root.lookup(["a", "b", "c", "d", "p", "xxx", "e", "f"])) and p[2] == (
        SourceSpec(["a", "b", "c", "d"], ["e", "f"], empty),
        PathSpec([".", "any"], []),
    )

    assert (p := root.lookup(["a", "b", "c", "d", "o", "p", "e", "f"])) and p[2] == (
        SourceSpec(["a", "b", "c", "d"], ["o", "p", "e", "f"], empty),
        PathSpec([".", "whirl"], []),
    )

    assert root.lookup(["a", "b", "c", "d", "rand"]) is None

    assert root.lookup(["a", "b", "c", "d", "xxx", "f"]) is None
