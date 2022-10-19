from pathlib import Path

import pytest

from kayaku.spec import (
    FormattedPath,
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
    assert parse_path("./config/modules/{}::config.{**}") == PathSpec(
        [".", "config", "modules", PathFill.SINGLE], ["config", PathFill.EXTEND]
    )


def test_parse_spec_err():
    with pytest.raises(ValueError):
        parse_source("*")
    with pytest.raises(ValueError):
        parse_path("{**}::{**}")


def test_format_path_spec():
    base_pth = Path("./temp/spec/").resolve()
    base_pth.mkdir(parents=True, exist_ok=True)
    assert parse_path(base_pth.as_posix() + "/{}::config.{**}.{}.mock").format(
        ["a", "b", "c", "d"]
    ) == FormattedPath(Path(base_pth / "a"), ["config", "b", "c", "d", "mock"])

    assert parse_path(base_pth.as_posix() + "/{}::config.{}.mock").format(
        ["a", "b"]
    ) == FormattedPath(Path(base_pth / "a"), ["config", "b", "mock"])

    assert parse_path(base_pth.as_posix() + "/{**}::config.{}.{}.mock").format(
        ["a", "b", "c", "d"]
    ) == FormattedPath(Path(base_pth / "a/b"), ["config", "c", "d", "mock"])

    assert (
        parse_path(base_pth.as_posix() + "/{}:config.{}.mock").format(
            ["a", "b", "c", "d"]
        )
        is None
    )
    assert parse_path(base_pth.as_posix() + "/{**}").format(
        ["a", "b", "c"]
    ) == FormattedPath(Path(base_pth / "a/b/c"), [])
