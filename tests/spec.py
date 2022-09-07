import pytest

from kayaku.spec import (
    PathFill,
    PathSpec,
    SectionSpec,
    SourceSpec,
    parse_path,
    parse_source,
)


def test_spec_parse():
    assert parse_source("{module.**}.secrets") == SourceSpec(
        ["module"], ["secrets"], SectionSpec(["module"], [])
    )

    assert parse_source("graia.{**}") == SourceSpec(["graia"], [], SectionSpec([], []))
    assert parse_path("./config/modules/{}:config.{**}") == PathSpec(
        [".", "config", "modules", PathFill.SINGLE], ["config", PathFill.EXTEND]
    )


def test_parse_spec_err():
    with pytest.raises(ValueError):
        parse_source("*")
    with pytest.raises(ValueError):
        parse_path("{**}:{**}")
    with pytest.raises(ValueError):
        parse_path("a::b")
