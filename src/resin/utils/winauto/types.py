"""
*`@file`* `resin/utils/winauto/types`
"""
from __future__ import annotations
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

class WindowClass(BaseStrEnum):
    """
    ```
    POPUP = "#32768"
    DIALOG = "#32770"
    ```
    """
    POPUP = "#32768"
    DIALOG = "#32770"

__all__ = export(DesktopBackend, WindowClass)