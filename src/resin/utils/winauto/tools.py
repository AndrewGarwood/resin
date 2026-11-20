"""
*`@file`* `utils/winauto/tools`
"""
from pywinauto.backend import name as _get_backend_name
from pyqi import export, require
from typing import Literal


def get_backend_name() -> str | Literal["win32", "uia"]:
    val = _get_backend_name()
    return require.non_empty_string(val, "backend.name()")

__all__ = export (
    get_backend_name
)