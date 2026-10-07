"""
*`@file`* `utils/winauto/control`
"""
from typing import (Any)
from pywinauto.base_wrapper import BaseWrapper
from pyqi import export
from .types import (ControlKey)

def get_control_key(ctrl: BaseWrapper | Any, /) -> ControlKey:
    ctrl_type = getattr(ctrl.element_info, "control_type", None)
    handle = getattr(ctrl.element_info, "handle", None)
    automation_id = getattr(ctrl.element_info, "automation_id", None)
    rect = ctrl.rectangle()
    return (str(ctrl_type), str(handle), str(automation_id), str(rect))

def control_is_available(ctrl: BaseWrapper | Any, /) -> bool:
    """ *`@returns`* `bool(ctrl) and ctrl.is_visible() and ctrl.is_enabled()` """
    return bool(ctrl) and ctrl.is_visible() and ctrl.is_enabled()

__all__ = export(get_control_key, control_is_available)