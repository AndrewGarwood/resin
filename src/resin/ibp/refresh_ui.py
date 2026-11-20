"""
*`@file`* `ibp/refresh_ui`
"""
from pathlib import Path
from typing import (Any, Protocol)
from resin.utils import (winauto)
from resin._workbook import (Deadline)
from .constants import IBP_RIBBON_TITLE
from pyqi import export
from lute import get_logger, LogMsg
mlog = get_logger(__file__)


class RefreshUI(Protocol):
    def refresh(
        self,
        workbook: Any,
        worksheet: Any,
        pid: int,
        path: Path,
        deadline: Deadline
    ) -> None: ...


class RibbonRefreshUI(RefreshUI):
    def __init__(
        self,
        ribbon_tab_title: str = IBP_RIBBON_TITLE,
        refresh_btn_title: str = "Refresh",
    ) -> None:
        self.ribbon_tab_title = ribbon_tab_title
        self.refresh_btn_title = refresh_btn_title

    def refresh(
        self, 
        workbook: Any, 
        worksheet: Any, 
        pid: int, 
        path: Path, 
        deadline: Deadline,
        hwnd: int | None = None
    ) -> None:
        deadline.check("IBP Refresh UI activation")
        workbook.Activate()
        # worksheet.Activate()
        _dict = winauto.WindowOptionsDict(process=pid, title_re=rf"^{path.name}.*")
        if (hwnd is not None):
            _dict['handle'] = hwnd
        window = winauto.find_window(_dict)
        # _, window = winauto.attach_process_to_window(pid, path.name)
        raise NotImplementedError("oi I can't find da tab item")
        deadline.check("Select IBP Ribbon Tab")
        window.wait_for_idle()
        # try: window.restore() # type: ignore
        # except Exception: pass
        window.set_focus()
        # _ctrl_types = (
        #         winauto.UiaControl.TAB_ITEM, 
        #         winauto.CommonControl.BUTTON, 
        #         winauto.UiaControl.TEXT,
        #     )
        tab = winauto.find_window(
            winauto.WindowOptionsDict(
                process=pid,
                title_re=self.ribbon_tab_title,
                top_level_only=False
            )
        )
        # for c in _ctrl_types:
        #     mlog.debug(LogMsg(
        #         f"@ ctrl_type {c}",
        #         f"{winauto.window.get_class(class_name=winauto.Win32Window.DIALOG, visible_only=True)=}"
        #     ))
        # tab = winauto.window.find_available_control(
        #     window,
        #     title=self.ribbon_tab_title,
        #     ctrl_types=(
        #         winauto.UiaControl.TAB_ITEM, 
        #         winauto.CommonControl.BUTTON, 
        #         winauto.UiaControl.TEXT,
        #     )
        # )
        tab.wait_for_idle()
        tab.click_input()
        deadline.check("Find refresh button")
        refresh_btn = winauto.window.find_available_control(
            window, 
            title=self.refresh_btn_title,
            ctrl_types=winauto.CommonControl.BUTTON
        )
        refresh_btn.wait_for_idle()
        deadline.check("Dispatch IBP refresh with click input")
        refresh_btn.click_input()
        return None

__all__ = export(RefreshUI, RibbonRefreshUI)