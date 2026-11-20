"""
*`@file`* `utils/winauto/window/options`
"""
from typing import (TypedDict)
from pywinauto.element_info import ElementInfo

class WindowOptionsDict(TypedDict, total=False):
    """
    subset of `kwargs` used in `pywinauto.findwindows.find_elements()` 
    - not gonna make corresponding `Json.Serial` class for now.
    """
    title: str
    title_re: str
    class_name: str
    class_name_re: str
    top_level_only: bool
    visible_only: bool
    enabled_only: bool
    active_only: bool
    handle: int
    parent: int | ElementInfo
    """
    parent's `handle (integer)` or `pywinauto.element_info.ElementInfo`
    """
    process: int
    """
    the target `process_id`
    """

__all__ = [
    "WindowOptionsDict"
]