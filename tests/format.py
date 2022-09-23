import inspect
from typing import Any, Dict, List

import pytest
from pydantic import BaseModel

from kayaku import backend as json5
from kayaku.doc_parse import store_field_description
from kayaku.format import format_with_model
from kayaku.pretty import Prettifier


def test_format_model():
    class Model(BaseModel):
        a: int = 4
        """Annotation: A"""
        b: Dict[str, str] = {"a": "c"}
        """B
        Annotation: B
        """
        c: List[str]
        "Fantasy C"
        e: Any
        "Any E"

    store_field_description(Model)

    data = json5.loads(
        """
{
    /*
    * Annotation: A
    *
    * @type: int
    */
    a: 3,
    d: 5,
    c: ["123"]
    /*
    * B
    * Annotation: B
    * 
    * @type: Mapping[str, str]
    */
}
"""
    )

    format_with_model(data, Model)

    assert json5.dumps(Prettifier().prettify(data)) == inspect.cleandoc(
        """\
        {
            /*
            * Annotation: A
            * 
            * @type: int
            */
            "a": 3,
            "d": 5,
            /*
            * Fantasy C
            * 
            * @type: List[str]
            */
            /*
            * B
            * Annotation: B
            * 
            * @type: Mapping[str, str]
            */
            "c": ["123"],
            "b": {"a": "c"},
            /*
            * Any E
            * 
            * @type: Optional[Any]
            */
            "e": null
        }
        """
    )

    with pytest.raises(TypeError):
        format_with_model({}, Model)