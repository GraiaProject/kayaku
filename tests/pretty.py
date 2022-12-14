import inspect

from kayaku import backend as json5
from kayaku.backend.types import Quote, convert
from kayaku.pretty import Prettifier


def test_pretty_single_wrapped():
    origins = [convert(i) for i in [{"a": "b"}, {"a": 1}, [1], ["acc"], [], {}]]
    expected = ["""{"a": "b"}""", """{"a": 1}""", """[1]""", """["acc"]""", "[]", "{}"]

    for o, e in zip(origins, expected):
        assert json5.dumps(Prettifier().prettify(o)) == e


def test_pretty_single_unwrapped():
    origin = convert({"a": "b"})
    expected_unwrapped = inspect.cleandoc(
        """\
        {
            "a": "b"
        }
        """
    )
    assert (
        json5.dumps(Prettifier(unfold_single=True).prettify(origin))
        == expected_unwrapped
    )
    origin = convert({"a": 1})
    expected_unwrapped = inspect.cleandoc(
        """\
        {
            "a": 1
        }
        """
    )
    assert (
        json5.dumps(Prettifier(unfold_single=True).prettify(origin))
        == expected_unwrapped
    )


def test_pretty_complex():
    obj = {"a": 5, "b": 6, "c": [None, {"a": "b", "c": {"d": "e"}}, "F"]}
    result = inspect.cleandoc(
        """\
        {
            "a": 5,
            "b": 6,
            "c": [
                null,
                {
                    "a": "b",
                    "c": {"d": "e"}
                },
                "F"
            ]
        }
        """
    )
    assert json5.dumps(Prettifier().prettify(convert(obj))) == result


def test_pretty_flavor():
    input_str = "{a: 6}"
    assert (
        json5.dumps(Prettifier(key_quote=None).prettify(json5.loads(input_str)))
        == "{a: 6}"
    )
    assert (
        json5.dumps(Prettifier(key_quote=Quote.DOUBLE).prettify(json5.loads(input_str)))
        == '{"a": 6}'
    )
    assert (
        json5.dumps(Prettifier(key_quote=Quote.SINGLE).prettify(json5.loads(input_str)))
        == "{'a': 6}"
    )
    assert (
        json5.dumps(Prettifier(key_quote=False).prettify(json5.loads("{'a': 6}")))
        == "{a: 6}"
    )
    assert (
        json5.dumps(Prettifier(key_quote=False).prettify(json5.loads("{'.': 6}")))
        == '{".": 6}'
    )


def test_pretty_comment():
    input_str = """
    {
        "a": 5,
        "b": 6,
        "c": [
            null,
            /*massive*/{ //plots
                "a": "b",
                "c": {"d": "e"}
            },
            "F", // marvelous
        ],
        "ariadne":{
            /*
            More annotations


            @type: int
             */
            "account": 0
        },
        "broadcast":{
            /*@type: List[dict]*/
            "dct":[
                {"3": 5} // what a mess
            ] /*input*/,
        /*
                 * Test annotating
                 * contain '*' and '/'
             * shorter ident
                         * longer ident
                 *
                 * @type: Optional[P]
                                */
            "p": null
        }, // bro
    }
    """

    output = inspect.cleandoc(
        """\
        {
            "a": 5,
            "b": 6,
            "c": [
                null,
                /*massive*/
                { //plots
                    "a": "b",
                    "c": {"d": "e"}
                },
                "F" // marvelous
            ],
            "ariadne": {
                /*
                 * More annotations
                 *
                 *
                 * @type: int
                 */
                "account": 0
            },
            "broadcast": {
                /*@type: List[dict]*/
                /*input*/
                "dct": [
                    {"3": 5} // what a mess
                ],
                /*
                 * Test annotating
                 * contain '*' and '/'
                 * shorter ident
                 * longer ident
                 *
                 * @type: Optional[P]
                 */
                "p": null
            } // bro
        }
        """
    )

    assert json5.dumps(Prettifier().prettify(json5.loads(input_str))) == output
