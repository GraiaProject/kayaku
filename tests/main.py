import shutil
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Union

import pytest

import kayaku
import kayaku.domain
import kayaku.storage
from kayaku import bootstrap, config, create, initialize, save, save_all
from kayaku.backend import loads
from kayaku.pretty import Prettifier
from kayaku.schema_gen import SchemaGenerator


@contextmanager
def start_over():
    base_pth = Path("./temp/full_test").resolve()
    base_pth.mkdir(parents=True, exist_ok=True)
    kayaku.domain._store = kayaku.domain._GlobalStore(Prettifier, SchemaGenerator)
    kayaku.storage._root.set(kayaku.storage._PrefixNode())
    kayaku.initialize({"{**}": base_pth.as_posix() + "/{}::{**}"})
    yield
    shutil.rmtree(base_pth.as_posix())


def test_main():

    start_before_init()
    empty_location_report()

    test_cases = [
        init_fail,
        field_name_collision,
        bootstrap_fail,
        nested_model,
        repl_test,
        basic_test,
        occupy_test,
        reload_test,
        invalid_conf_cls,
    ]
    for case in test_cases:
        with start_over():
            case()


def start_before_init():
    with pytest.raises(RuntimeError):

        @config("config")
        class Conf:
            a: int


def invalid_conf_cls():
    with pytest.raises(ValueError):

        @config("")
        class Conf:
            a: int

    @dataclass
    class InvalidConfigModel:
        a: int

    with pytest.raises(TypeError):
        create(InvalidConfigModel)


def empty_location_report():
    kayaku.domain._store = kayaku.domain._GlobalStore(Prettifier, SchemaGenerator)
    with pytest.raises(ValueError):

        @config("domain.conf.1")
        class Conf:
            a: int


def init_fail():
    with pytest.raises(ValueError):
        kayaku.initialize({"": ""})


def field_name_collision():
    kayaku.initialize(
        {
            "sub.a.{**}": "./temp/full_test/collision",
            "sub.b.{**}": "./temp/full_test/collision",
        }
    )

    @config("sub.a")
    class A:
        a: int

    with pytest.raises(NameError):

        @config("sub.b")
        class B:
            a: int


def bootstrap_fail():
    @config("account")
    class AccountConf:
        account: Union[int, str]
        """Account, int for UserID, str for username."""
        password: str

    with pytest.raises(ValueError):
        bootstrap()


def nested_model():
    @dataclass
    class Sub1:
        a: int = 5
        b: int = 6

    @config("conf.nested.bootstrap")
    class Parent:
        sub1: Sub1 = field(default_factory=Sub1)
        f: int = 5

    @config("conf.nested.other")
    class Other:
        important: bool = True

    save(Other)
    save(create(Other))

    bootstrap()
    save_all()
    assert loads(Path("./temp/full_test/conf.jsonc").read_text()) == {
        "nested": {
            "bootstrap": {
                "f": 5,
                "sub1": {
                    "a": 5,
                    "b": 6,
                },
            },
            "other": {
                "important": True,
            },
        },
        "$schema": Path("./temp/full_test/conf.schema.json").resolve().as_uri(),
    }


def basic_test():
    account_pth = Path("./temp/full_test/account.jsonc").resolve()

    account_pth.touch(exist_ok=True)

    account_pth.write_text("""{"account": "admin@graia", "password": "login_weak"}""")

    @config("account")
    class AccountConf:
        account: Union[int, str]
        """Account, int for UserID, str for username."""
        password: str = ""

    create(AccountConf)

    sub_pth = Path("./temp/full_test/subscription.jsonc")

    sub_pth.write_text(
        """
{
    "organizations": ["GraiaProject", "GraiaCommunity"],
}
"""
    )

    @config("subscription")
    class SubConf:
        organizations: List[str] = field(default_factory=list)
        """Organizations that you want to subscribe (tracks *all* repo events)"""

        repos: List[str] = field(default_factory=list)
        """Repositories that you want to subscribe
        Please avoid duplicating the organizations that you've subscribed.
        """

    save_all()

    bootstrap()
    account = create(AccountConf)
    account_copy = create(AccountConf)
    assert account is account_copy
    assert account.account == "admin@graia"
    assert account.password == "login_weak"

    sub_conf = create(SubConf)
    save_all()

    sub_conf.repos.append("GreyElaina/richuru")
    save(SubConf)
    sub_conf = create(SubConf, flush=True)
    assert sub_conf.repos == ["GreyElaina/richuru"]

    assert (
        sub_pth.read_text()
        == f"""\
{{
    /*
    * Organizations that you want to subscribe (tracks *all* repo events)
    *
    * @type: List[str]
    */
    "organizations": [
        "GraiaProject",
        "GraiaCommunity"
    ],
    /*
    * Repositories that you want to subscribe
    * Please avoid duplicating the organizations that you've subscribed.
    *
    * @type: List[str]
    */
    "repos": ["GreyElaina/richuru"],
    "$schema": "{sub_pth.with_name("subscription.schema.json").resolve().as_uri()}"
}}
"""
    )

    assert (
        account_pth.read_text()
        == f"""\
{{
    /*
    * Account, int for UserID, str for username.
    *
    * @type: Union[int, str]
    */
    "account": "admin@graia",
    /*@type: str*/
    "password": "login_weak",
    "$schema": "{account_pth.with_name("account.schema.json").resolve().as_uri()}"
}}
"""
    )


def occupy_test():
    @config("subscription")
    class SubConf:
        organizations: List[str] = field(default_factory=list)
        """Organizations that you want to subscribe (tracks *all* repo events)"""

        repos: List[str] = field(default_factory=list)
        """Repositories that you want to subscribe
        Please avoid duplicating the organizations that you've subscribed.
        """

    with pytest.raises(NameError):

        @config("subscription")
        class SubConf2:
            organizations: List[str] = field(default_factory=list)
            """Organizations that you want to subscribe (tracks *all* repo events)"""

            repos: List[str] = field(default_factory=list)
            """Repositories that you want to subscribe
            Please avoid duplicating the organizations that you've subscribed.
            """


def repl_test():
    class SubConf:
        organizations: List[str] = field(default_factory=list)
        """Organizations that you want to subscribe (tracks *all* repo events)"""

    SubConf.__module__ = "_sre"  # Fake it as a non-retrievable class
    config("subscription")(SubConf)


def reload_test():

    sub_pth = Path("./temp/full_test/subscription.jsonc")
    sub_pth.write_text(
        """
{
    "organizations": ["GraiaProject", "GraiaCommunity"],
    "repos": ["GreyElaina/richuru"],
}
"""
    )

    # Initial creation
    @config("subscription")
    class SubConf:
        organizations: List[str] = field(default_factory=list)
        """Organizations that you want to subscribe (tracks *all* repo events)"""

    # Reload without instantiate
    @config("subscription")
    class SubConf:
        organizations: List[str] = field(default_factory=list)
        """Organizations that you want to subscribe (tracks *all* repo events)"""

    inst1 = create(SubConf)
    assert asdict(inst1) == {
        "organizations": ["GraiaProject", "GraiaCommunity"],
    }

    sub_pth.write_text(
        """
{
    "organizations": ["GraiaProject", "GraiaCommunity", "OctoOrg"],
    "repos": ["GreyElaina/richuru"],
}
"""
    )

    assert sys.getrefcount(inst1) == 3

    # Reload, without changes
    @config("subscription")
    class SubConf:
        organizations: List[str] = field(default_factory=list)
        """Organizations that you want to subscribe (tracks *all* repo events)"""

    inst2 = create(SubConf)
    assert asdict(inst2) == {
        "organizations": ["GraiaProject", "GraiaCommunity", "OctoOrg"],
    }

    assert inst1 is not inst2
    del inst1, inst2

    # Change schema
    @config("subscription")
    class SubConf:
        organizations: List[str] = field(default_factory=list)
        """Organizations that you want to subscribe (tracks *all* repo events)"""

        repos: List[str] = field(default_factory=list)
        """Repositories that you want to subscribe
        Please avoid duplicating the organizations that you've subscribed.
        """

    assert asdict(create(SubConf)) == {
        "organizations": ["GraiaProject", "GraiaCommunity", "OctoOrg"],
        "repos": ["GreyElaina/richuru"],
    }
