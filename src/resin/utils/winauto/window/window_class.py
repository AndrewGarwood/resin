"""
*`@file`* `utils/winauto/window/window_class`
"""

from typing import Any, Callable
import time
from resin.utils.winauto.types import (DesktopBackend)
from resin.utils.winauto.debug import (element_info)
from resin.utils.winauto import control
from resin.utils.winauto.exceptions import (AutomationError)
from pywinauto import Application, Desktop
from pywinauto.base_wrapper import BaseWrapper
from pyqi import (
    require, Array, String, 
    export, Arbitrary, resolve_arbitrary
    )
from lute import (get_logger, LogMsg)

mlog = get_logger(__file__, name_depth=1)



def get_class(
    *,
    backend: DesktopBackend | str | None=None,
    class_name: control.Win32Window | str,
    visible_only: bool,
    
) -> list[Any]:
    return (
        Desktop(backend=backend)
        .windows(
            class_name=class_name, 
            visible_only=visible_only
        )
    )

def class_exists(
    *,
    backend: DesktopBackend | str | None=None,
    class_name: control.Win32Window | str,
    visible_only: bool,
) -> bool:
    items = get_class(
        class_name=class_name, 
        backend=backend, 
        visible_only=visible_only
    )
    return len(items) > 0


def wait_for_class(
    *,
    backend: DesktopBackend | str | None=None,
    class_name: control.Win32Window | str,
    visible_only: bool = True,
    timeout: float = 2.0, 
    poll: float = 0.05,
    selector: Callable[..., Any] | None = None
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
            return items[0] if not selector else selector(items)
        time.sleep(poll)
    return None

def dump_class(
    *,
    backend: DesktopBackend | str | None=None,
    class_name: control.Win32Window | str,
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
                f"@ element ({i+1} / {N})",
                **element_info(w)
            ))
        except Exception as e:
            mlog.warning(LogMsg.err(
                e,
                f"<failed to inspect {class_name}>",
                index=i
            ))
    return None


__all__ = export(
    wait_for_class, 
    dump_class, 
    get_class, 
    class_exists
)