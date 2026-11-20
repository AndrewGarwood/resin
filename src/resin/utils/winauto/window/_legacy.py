"""
*`@file`* `utils/winauto/window/_legacy`
"""
from typing import Any

from resin.utils.winauto import control
from resin.utils.winauto.exceptions import (AutomationError)
from pywinauto import Application
from pywinauto.base_wrapper import BaseWrapper
from pyqi import (
    Array, String, 
    export, Arbitrary, resolve_arbitrary
    )
from lute import (get_logger, LogMsg)

mlog = get_logger(__file__, name_depth=1)


def find_available_control(
    window: BaseWrapper,
    /,
    title: str,
    ctrl_types: Arbitrary[control.ControlClass],
    require_unique: bool=True
) -> BaseWrapper:
    ctrl_types = resolve_arbitrary(ctrl_types)
    matches: list[BaseWrapper] = []
    try:        
        for control_type in ctrl_types:
            matches.extend(Array.filter(
                window.descendants(
                    title=title, 
                    control_type=str(control_type)
                ),
                control.is_available
            ))
        unique_ctrls: dict[control.ControlKey, BaseWrapper] = {
            control.generate_key(ctrl): ctrl
            for ctrl in matches
        }
        candidates = list(unique_ctrls.values())
        if not candidates:
            raise AutomationError(f"No visible & enabled controls found")
        if require_unique and len(candidates) > 1:
            raise AutomationError(LogMsg(
                f"Multiple controls found for given title.",
                controls_found=list(unique_ctrls.keys())
            ))
        return candidates[0]
    except Exception as e:
        raise RuntimeError(LogMsg.err(
            e,
            title=title,
            ctrl_types=ctrl_types,
            require_unique=require_unique,
            available_descendants=("[\n" 
                + "\n".join(Array.map(matches, str)))
                + "\n]"
        )) from e


def find_window_by_title(
    app: Application,
    title: str,
    /,
    require_unique: bool=True,
    ignore_case: bool=True,
    window_ctrl_type: str = "Window"
) -> BaseWrapper:
    try:
        if ignore_case: title = title.casefold()
        candidates: list[BaseWrapper] = Array.filter(
            app.windows(), 
            lambda w: str(w.element_info.control_type) == window_ctrl_type
        )
        matches = Array.filter(
            candidates, 
            lambda x: String.contains(str(x.window_text()), title, ignore_case=True)
        )
        if not matches:
            raise AutomationError(LogMsg(
                f"Unable to find window of target", 
                available_window_titles=Array.map(
                    candidates, 
                    lambda x: str(x.window_text())
                )
            ))
        if require_unique and len(matches) > 1:
            raise AutomationError(LogMsg(
                f"Multiple windows matched target:", 
                matches=Array.map(matches, lambda x: str(x.window_text()))
            ))
        return matches[0]
    except Exception as e:
        raise RuntimeError(LogMsg.err(
            e,
            title=title,
            require_unique=require_unique,
            ignore_case=ignore_case,
            backend=str(app.backend)
        )) from e

__all__ = export(
    find_window_by_title, 
    find_available_control
)