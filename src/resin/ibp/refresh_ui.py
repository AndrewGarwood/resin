"""
*`@file`* `ibp/refresh_ui`
"""
from pathlib import Path
from typing import (Any, Protocol)
from resin.utils import (winauto)
from resin._workbook import (Deadline)
from .constants import IBP_RIBBON_TITLE
from pyqi import export


class RefreshUI(Protocol):
    def refresh(
        self,
        workbook: Any,
        worksheet: Any,
        pid: int,
        path: Path,
        backend: winauto.DesktopBackend,
        deadline: Deadline
    ) -> None: ...


class RibbonRefreshUI(RefreshUI):
    def __init__(
        self,
        ribbon_tab_title: str = IBP_RIBBON_TITLE,
        refresh_btn_title: str = "Refresh",
        ribbon_title: str = "Ribbon",
    ) -> None:
        self.ribbon_title = ribbon_title
        self.ribbon_tab_title = ribbon_tab_title
        self.refresh_btn_title = refresh_btn_title

    def refresh(
        self, 
        workbook: Any, 
        worksheet: Any, 
        pid: int, 
        path: Path, 
        backend: winauto.DesktopBackend, 
        deadline: Deadline
    ) -> None:
        deadline.check("IBP Refresh UI activation")
        workbook.Activate()
        worksheet.Activate()
        _, window = winauto.attach_to_process_window(
            pid, 
            path.name, 
            backend=backend, 
            require_unique=True, 
            ignore_case=True, 
            timeout_seconds=deadline.remaining()
        )
        deadline.check("Select IBP Ribbon Tab")
        window.wait_for_idle()
        try: window.restore() # type: ignore
        except Exception: pass
        window.set_focus()
        tab = winauto.find_available_control(
            window,
            title=self.ribbon_tab_title,
            ctrl_types=(
                winauto.UiaControl.TAB_ITEM, 
                winauto.CommonControl.BUTTON, 
                winauto.UiaControl.TEXT
            )
        )
        tab.wait_for_idle()
        tab.click_input()
        deadline.check("Find refresh button")
        refresh_btn = winauto.find_available_control(
            window, 
            title=self.refresh_btn_title,
            ctrl_types=winauto.CommonControl.BUTTON
        )
        refresh_btn.wait_for_idle()
        deadline.check("Dispatch IBP refresh with click input")
        refresh_btn.click_input()
        return None

__all__ = export(RefreshUI, RibbonRefreshUI)