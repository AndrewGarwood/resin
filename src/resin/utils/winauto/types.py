"""
*`@file`* `resin/utils/winauto/types`
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, TypeAlias
from pyqi import BaseStrEnum, export
from .control.types import Win32Window as WindowClass


class DesktopBackend(BaseStrEnum):
    """
    ```
    UIA = "uia"
    WIN32 = "win32"
    ```
    """
    UIA = "uia"
    WIN32 = "win32"

__all__ = export(
    DesktopBackend, WindowClass, 
)