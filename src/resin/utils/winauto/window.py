"""
*`@file`* `utils/winauto/window`
"""
from pywinauto import Desktop
import time
from .types import (WindowClass, DesktopBackend)
from . import control
from .exceptions import AutomationError
from pywinauto import Application
from pywinauto.base_wrapper import BaseWrapper
from pyqi import (FlexStr, require, Array, String, export)

import lute
LogMsg = lute.LogMsg
mlog = lute.get_logger(__file__, name_depth=1)


def get_class(
    *,
    backend: FlexStr[DesktopBackend],
    class_name: FlexStr[WindowClass],
    visible_only: bool,
    
) -> list:
    return (Desktop(backend=backend)
        .windows(class_name=class_name, visible_only=visible_only)
    )

def class_exists(
    backend: FlexStr[DesktopBackend],
    class_name: FlexStr[WindowClass],
    visible_only: bool,
):
    return bool(get_class(
        class_name=class_name, backend=backend, visible_only=visible_only
    ))

def wait_for_class(
    *,
    backend: FlexStr[DesktopBackend],
    class_name: FlexStr[WindowClass],
    visible_only: bool,
    timeout: float = 2.0, 
    poll: float = 0.05,
):
    timeout=require.positive_number(timeout, "timeout")
    poll=require.positive_number(poll, "poll")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        items = get_class(
            backend=backend, 
            class_name=class_name, 
            visible_only=visible_only
        )
        if items:
            return items[0]
        time.sleep(poll)
    return None


def dump_class(
    backend: FlexStr[DesktopBackend],
    class_name: FlexStr[WindowClass],
    visible_only: bool=True
) -> None:
    items = get_class(
        backend=backend, 
        class_name=class_name, 
        visible_only=visible_only
    )
    N = len(items)
    for i, w in enumerate(items):
        try:
            mlog.debug(LogMsg(
                f"@ popup_menu ({i+1} / {N})",
                title=f"{w.window_text()!r}",
                class_name=f"{w.class_name()!r}",
                handle=f"{w.handle}",
                rectangle=f"{w.rectangle()}"
            ))
        except Exception as e:
            mlog.warning(LogMsg.err(e, f"<failed to inspect popup menu>"))
    return None


def find_available_control(
    window: BaseWrapper,
    /,
    title: str,
    ctrl_types: tuple[control.ControlClass, ...],
    require_unique: bool=True
) -> BaseWrapper:
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
        raise Exception(LogMsg.err(
            e,
            title=title,
            ctrl_types=ctrl_types,
            require_unique=require_unique
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
                f"Multiple windows matched target", 
                matches=Array.map(matches, lambda x: str(x.window_text()))
            ))
        return matches[0]
    except Exception as e:
        raise Exception(LogMsg.err(
            e,
            title=title,
            require_unique=require_unique,
            ignore_case=ignore_case
        )) from e

def attach_to_process_window(
    pid: int, 
    title: str, 
    /,
    backend: DesktopBackend, 
    require_unique: bool=True,
    ignore_case: bool=True,
    timeout_seconds: float=30.0,
) -> tuple[Application, BaseWrapper]:
    app = Application(
        backend=str(backend)
    ).connect(
        process=pid,
        timeout=timeout_seconds
    )
    window = find_window_by_title(
        app, 
        title, 
        require_unique=require_unique, 
        ignore_case=ignore_case
    )
    return (app, window)

__all__ = export(
    get_class, 
    class_exists, 
    wait_for_class, 
    dump_class, 
    find_window_by_title, 
    find_available_control,
    attach_to_process_window
    )