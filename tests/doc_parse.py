from pydantic import BaseModel

from kayaku.doc_parse import extract_field_docs


def test_extract_attr_docs():
    class M(BaseModel):
        a: int = 5  # undocumented
        b = 6
        """b document"""
        c: int = 7
        "c document"

    res = extract_field_docs(M)
    assert {k: doc for k, (_, doc) in res.items()} == {
        "a": None,
        "b": "b document",
        "c": "c document",
    }
