import io

test_input = """\
{
    "base":{
        /*
        * More annotations
        * 
        * @type: int
        */
        "account": 0
    },
    "next":{
        /*@type: List[dict]*/
        "dct":[
            {"3": 5}
        ],
        /*
        * Test annotating
        * What about double line
        * 
        * @type: Optional[P]
        */
        "p": null,
        "q": true, // attempt
        "v": false, /* wow */
        "s": "trail",
    },
    identifier: 'SINGLE',
    numbers: [+NaN, -Infinity, 0x7b],
    "$schema": "file:///F:/PythonProjects/Graiax/kayaku/config.schema.json"
}
"""


def test_backend_round_trip():
    import kayaku.backend.env
    from kayaku import backend

    in_io = io.StringIO(test_input)
    out_io = io.StringIO()

    assert backend.dumps(backend.loads(test_input)) == test_input
    backend.dump(backend.load(in_io), out_io)
    assert out_io.getvalue() == test_input

    backend.env.DEBUG.set(True)

    in_io = io.StringIO(test_input)
    out_io = io.StringIO()

    assert backend.dumps(backend.loads(test_input)) == test_input
    backend.dump(backend.load(in_io), out_io)
    assert out_io.getvalue() == test_input
