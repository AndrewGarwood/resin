"""
*`@file`* `resin/utils/winauto/types`
"""
from __future__ import annotations
from typing import (Any, TypedDict)
from pyqi import BaseStrEnum, export


class DesktopBackend(BaseStrEnum):
    """
    ```
    UIA = "uia"
    WIN32 = "win32"
    ```
    """
    UIA = "uia"
    WIN32 = "win32"

class ElementInfoDict(TypedDict, total=False):
    window_text: str | None
    class_name: str | None
    handle: int | str | None
    rectangle: Any | None
    is_visible: bool | str | None
    is_enabled: bool | str | None

__all__ = export(
    DesktopBackend, ElementInfoDict
)