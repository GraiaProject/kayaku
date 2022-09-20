from pydantic import BaseModel

from kayaku.doc_parse import store_field_description


def test_extract_attr_docs():
    class M(BaseModel):
        a: int = 5  # undocumented
        b = 6
        """b document"""
        c: int = 7
        "c document"

    store_field_description(M)
    assert {k: f.field_info.description for k, f in M.__fields__.items()} == {
        "a": None,
        "b": "b document",
        "c": "c document",
    }
