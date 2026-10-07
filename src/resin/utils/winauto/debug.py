"""
*`@file`* `resin/utils/winauto/debug`
"""
from pywinauto.base_wrapper import BaseWrapper
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
            window_text=f"{d.window_text()!r}",
            class_name=f"{d.class_name()!r}",
            handle=f"{d.handle!r}",
            is_visible=f"{d.is_visible()!r}",
            is_enabled=f"{d.is_enabled()!r}",
        )
        except Exception as e:
            msg = LogMsg.err(e, f"<failed to inspect descendant>")
        mlog.debug(msg)


__all__ = ["inspect_descendants"]