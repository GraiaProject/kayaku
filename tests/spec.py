import pytest

from kayaku.spec import BaseSpec, Pattern, PatternSpec


def test_spec_parse():
    assert Pattern("graia.ariadne").parse() == PatternSpec(
        ["graia", "ariadne"], None, BaseSpec([], None)
    )

    assert Pattern("{graia.ariadne}").parse() == PatternSpec(
        ["graia", "ariadne"], None, BaseSpec(["graia", "ariadne"], None)
    )

    assert Pattern("{graia.ariadne:loc}").parse() == PatternSpec(
        ["graia", "ariadne"], "loc", BaseSpec(["graia", "ariadne"], "loc")
    )

    assert Pattern("graia.{ariadne:loc}").parse() == PatternSpec(
        ["graia", "ariadne"], "loc", BaseSpec(["ariadne"], "loc")
    )

    assert Pattern("graia.{ariadne}:loc").parse() == PatternSpec(
        ["graia", "ariadne"], "loc", BaseSpec(["ariadne"], None)
    )

    assert Pattern(
        """graia.ariadne.{"sect.iops":"mutable.tag"}"""
    ).parse() == PatternSpec(
        ["graia", "ariadne", "sect.iops"],
        "mutable.tag",
        BaseSpec(["sect.iops"], "mutable.tag"),
    )

    assert Pattern(
        """graia.ariadne.{"sect.iops".pl:"mutable.tag"}"""
    ).parse() == PatternSpec(
        ["graia", "ariadne", "sect.iops", "pl"],
        "mutable.tag",
        BaseSpec(["sect.iops", "pl"], "mutable.tag"),
    )

    assert Pattern("graia.{ariadne.*}:loc").parse() == PatternSpec(
        ["graia", "ariadne"], "loc", BaseSpec(["ariadne"], None)
    )


def test_parse_spec_err():
    for spec in [
        "a..b",
        "a:b:c",
        "a:b.c",
        "a.{b}.{c}",
        "a.{{b}",
        "a.{c}}",
        "a.a{bc",
        "a.abc}",
        "a.{b}.c}",
    ]:
        with pytest.raises(ValueError):
            print(spec)
            Pattern(spec).parse()
