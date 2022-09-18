from importlib import import_module
from typing import Dict, cast

from .protocol import JSONModule

json: JSONModule = cast(JSONModule, import_module("..json", __name__))
jsonc: JSONModule = cast(JSONModule, import_module("..jsonc", __name__))
json5: JSONModule = cast(JSONModule, import_module("..json5", __name__))
