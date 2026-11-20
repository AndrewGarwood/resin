"""
*`@file`* `ibp/refresh_ui`
"""
from pathlib import Path
import re
import sys
from typing import (Protocol)
from resin.utils import (winauto)
from resin._workbook import (Deadline)
from win32com.client import CDispatch
from .constants import IBP_RIBBON_TITLE
from pyqi import export
from lute import (get_logger, LogMsg)
mlog = get_logger(__file__)


class RefreshUI(Protocol):
    """ 
    *`note`* only `backend == 'uia'` resulted in discoverable 
    ui elements to interact with
    """
    def refresh(
        self,
        workbook: CDispatch,
        worksheet: CDispatch,
        pid: int,
        *,
        deadline: Deadline,
        workbook_handle: int | None=None,
        backend=winauto.DesktopBackend.UIA
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
        workbook: CDispatch, 
        worksheet: CDispatch, 
        pid: int, 
        *,
        deadline: Deadline,
        workbook_handle: int | None = None,
        backend=winauto.DesktopBackend.UIA
    ) -> None:
        deadline.check("IBP Refresh UI activation")
        workbook.Activate()
        worksheet.Activate()
        app = winauto.connect_application(
            pid,
            backend=backend,
            timeout_seconds=deadline.remaining(),
        )
        criteria = (
            winauto.WindowOptionsDict(handle=workbook_handle)
            if workbook_handle is not None
            else winauto.WindowOptionsDict(title_re=rf"^{re.escape(workbook.Name)}.*")
        )
        window = app.window(**criteria)
        window.wait("ready", timeout=deadline.remaining())
        window.set_focus()
        tab = window.child_window(
            title=self.ribbon_tab_title,
            control_type=str(winauto.UiaControl.TAB_ITEM),
        )
        tab.wait("ready", timeout=deadline.remaining())
        deadline.check("Select IBP Ribbon Tab")
        tab.click_input()
        deadline.check("Find refresh button")
        refresh_btn = window.child_window(
            title=self.refresh_btn_title,
            control_type=str(winauto.CommonControl.BUTTON),
        )
        refresh_btn.wait("ready", timeout=deadline.remaining())
        deadline.check("Dispatch IBP refresh with click input")
        mlog.debug("Dispatching IBP Refresh click_input")
        refresh_btn.click_input()
        mlog.debug("IBP Refresh click_input returned")
        return None

__all__ = export(RefreshUI, RibbonRefreshUI)