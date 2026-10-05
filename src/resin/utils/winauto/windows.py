"""
*`@file`* `utils/winauto/windows`
"""
from pywinauto import Desktop
import time
from .types import (WindowClass, DesktopBackend)
from pyqi import (FlexStr, require)

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
    return bool(get_class(class_name=class_name, backend=backend, visible_only=visible_only))

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
