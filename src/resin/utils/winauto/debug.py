"""
*`@file`* `resin/utils/winauto/debug`
"""
from typing import Any
from pywinauto.base_wrapper import BaseWrapper

from .types import (ElementInfoDict)
from pyqi import export, safe

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

__all__ = export(inspect_descendants, element_info)