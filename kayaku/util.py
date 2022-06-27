import importlib.util
import sys


def exists_module(package: str) -> bool:
    return package in sys.modules or importlib.util.find_spec(package) is not None
