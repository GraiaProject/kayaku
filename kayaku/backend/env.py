from contextvars import ContextVar

DEBUG: ContextVar[bool] = ContextVar("kayaku.backend.json5.DEBUG", default=False)
