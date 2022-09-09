import pytest


def test_insert_spec():
    import kayaku.storage
    from kayaku.spec import PathSpec

    kayaku.storage.insert(
        ["a", "b", "c"], ["d", "e", "f"], PathSpec([".", "config"], [])
    )

    kayaku.storage.insert(
        ["a", "b", "c"], ["d", "e", "credential"], PathSpec([".", "credential"], [])
    )

    nd = kayaku.storage._root
    for key in ["a", "b", "c"]:
        nd = nd.nxt[key]

    assert nd.suffix
    suffix = nd.suffix
    for key in ["d", "e", "f"]:
        suffix = suffix.nxt[key]

    assert suffix.bound
    assert suffix.bound == PathSpec([".", "config"], [])

    suffix = nd.suffix
    for key in ["d", "e", "credential"]:
        suffix = suffix.nxt[key]

    assert suffix.bound
    assert suffix.bound == PathSpec([".", "credential"], [])

    with pytest.raises(ValueError):
        kayaku.storage.insert(
            ["a", "b", "c"], ["d", "e", "credential"], PathSpec([".", "credential"], [])
        )

    kayaku.storage._root = kayaku.storage._PrefixNode()
