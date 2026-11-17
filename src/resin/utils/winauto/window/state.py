"""
*`@file`* `utils/winauto/window/state`
"""
from __future__ import annotations
from functools import cache
from pyqi import (BaseStrEnum)
from lute import LogMsg

class WindowState(BaseStrEnum):
    """
    ```
    EXISTS = "exists" # the window is a valid handle
    VISIBLE = "visible" # the window is not hidden
    ENABLED = "enabled" # the window is not disabled
    READY = "ready" # the window is visible and enabled
    ACTIVE = "active" # the window is active
    ```
    """
    EXISTS = "exists"
    VISIBLE = "visible"
    ENABLED = "enabled"
    READY = "ready"
    ACTIVE = "active"

    @classmethod
    @cache
    def available(cls):
        """
        `@cache`
        - *`@returns`* `cls.all_of(cls.EXISTS, cls.READY)` → `'exists ready'`
        """
        return cls.all_of(cls.EXISTS, cls.READY)

    @classmethod
    def all_of(cls, *args: WindowState):
        """
        *`@returns`* `" ".join(str(x) for x in args)`
        """
        if (not args):
            raise ValueError(LogMsg(
                f"must provide at least one WindowState"
            ))
        return " ".join(str(x) for x in args)


__all__ = [
    "WindowState",
]

