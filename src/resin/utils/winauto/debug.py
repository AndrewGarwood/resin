"""
*`@file`* `resin/utils/winauto/debug`
"""
from typing import Any
from pywinauto.base_wrapper import BaseWrapper
import win32gui, win32con
from .types import (ElementInfoDict)
from .ownership import (window_process_id, iter_owner_chain)
from pyqi import export, safe, Json

from lute import get_logger, LogMsg
mlog = get_logger(__file__, name_depth=1)


# could instead return list[str] or list[LogMsg]
def inspect_descendants(item: BaseWrapper, /) -> None:
    descendants = item.descendants()
    N = len(descendants)
    mlog.debug(LogMsg(
        f"Inspecting descendants for item:",
        window_text=f"{item.window_text()!r}",
        class_name=f"{item.class_name()!r}",
        handle=f"{item.handle!r}",
        num_descendants=N
    ))
    for i, d in enumerate(descendants, start=1):
        msg: LogMsg
        try:
            msg = LogMsg(
                f"@ descendant ({i} / {N})",
                **element_info(d)
            )
        except Exception as e:
            msg = LogMsg.err(e, f"<failed to inspect descendant>")
        mlog.debug(msg)

def element_info(el: Any, /) -> ElementInfoDict:
    return ElementInfoDict(
        window_text=repr(safe.invoke_method(el, "window_text")),
        class_name=repr(safe.invoke_method(el, "class_name")),
        handle=repr(safe.readattr(el, "handle")),
        is_visible=repr(safe.invoke_method(el, "is_visible")),
        is_enabled=repr(safe.invoke_method(el, "is_enabled")),
    )

def dump_owner_chain(hwnd: int, /) -> None:
    current = hwnd
    i: int = 0
    while current:
        _info = {
            "hwnd": current,
            "title": win32gui.GetWindowText(current),
            "class_name": win32gui.GetClassName(current),
            "enabled": win32gui.IsWindowEnabled(current),
            "visible": win32gui.IsWindowVisible(current),
        }
        mlog.debug(LogMsg(
            f"@ iteration {i}",
            Json.stringify(_info)
        ))
        current = win32gui.GetWindow(current, win32con.GW_OWNER)
        i+=1
    return None

def describe_window(hwnd: int) -> dict[str, object]:
    owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)

    return {
        "hwnd": hwnd,
        "title": win32gui.GetWindowText(hwnd),
        "class_name": win32gui.GetClassName(hwnd),
        "owner_hwnd": owner or None,
        "owner_title": win32gui.GetWindowText(owner) if owner else None,
        "owner_chain": list(iter_owner_chain(hwnd)),
        "process_id": window_process_id(hwnd),
        "visible": bool(win32gui.IsWindowVisible(hwnd)),
        "enabled": bool(win32gui.IsWindowEnabled(hwnd)),
    }

__all__ = export(inspect_descendants, element_info, dump_owner_chain, describe_window)