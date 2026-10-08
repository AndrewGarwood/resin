"""
*`@file`* `gui/services/_export/types`
"""
from __future__ import annotations

from dataclasses import dataclass, field as _field
import time
from pathlib import Path
from typing import (Any, Callable, Iterable, Sequence, TypeAlias, TypedDict)
from pyqi import (Array, export)
from pyqi.models import (RetryOptions, RetryOptionsDict)
from lute import LogMsg, get_logger
from pywinauto import Desktop
from pywinauto.base_wrapper import BaseWrapper
from resin.utils.winauto.watcher import (NativeDialogWatcher)
from resin.utils.winauto import (DesktopBackend, 
    Win32Window, ControlOptions
)

mlog = get_logger(__file__, name_depth=2)





DialogControl: TypeAlias = Any

@dataclass
class NativeSaveDialogOptions:
    outpath: Path
    save_dialog_selector: Callable[[Iterable[DialogControl]], DialogControl]
    save_dialog: ControlOptions
    save_btn: ControlOptions
    overwrite_dialog: ControlOptions
    overwrite_btn: ControlOptions
    retry: RetryOptions = _field(default_factory=RetryOptions)
    backend: DesktopBackend = DesktopBackend.WIN32


@dataclass
class DepNativeSaveDialogOptions():
    outpath: Path
    save_dialog_selector: Callable[[Iterable[DialogControl]], DialogControl]
    """ e.g. 
    `def select_largest_edit(edits): return max(edits, key=lambda e: e.rectangle().width()) `
    """
    retry_func: Callable[[DialogControl, str, RetryOptions | None], bool] | None = None
    backend: DesktopBackend = DesktopBackend.WIN32
    edit_classname: str = "Edit"
    btn_classname: str = "Button"
    save_btn_patterns: list[str] = _field(default_factory=list)
    """
    defaults to 
    `[ r"^.*Save.*$", r"^&Save$", r"^Save$", r"^&Open$", r"^Open$", r"^OK$"]`
    """
    overwrite_window_classname: str = Win32Window.DIALOG.value
    overwrite_title_patterns: list[str] = _field(default_factory=list)
    """
    defaults to 
    `[ r".*Confirm Save As.*", r".*Save As.*", r".*already exists.*", r".*Confirm.*",]`
    """
    overwrite_btn_titles: list[str] = _field(default_factory=list)
    """ defaults to 
    `["Yes", "&Yes", "Replace", "&Replace", "OK"]`
    """
    def __post_init__(self):
        if (not self.save_btn_patterns):
            self.save_btn_patterns = [
                r"^.*Save.*$",
                r"^&Save$",
                r"^Save$",
                r"^&Open$",
                r"^Open$",
                r"^OK$",
            ]
        if (not self.overwrite_title_patterns):
            self.overwrite_title_patterns = [
                r".*Confirm Save As.*",
                r".*Save As.*",
                r".*already exists.*",
                r".*Confirm.*",
            ]
        if (not self.overwrite_btn_titles):
            self.overwrite_btn_titles = ["Yes", "&Yes", "Replace", "&Replace", "OK"]

    def confirm_overwrite(self, *, timeout: float=5.0) -> None:
        desktop = Desktop(backend=self.backend.value)
        for pat in self.overwrite_title_patterns:
            try:
                dlg = desktop.window(
                    class_name=self.overwrite_window_classname, 
                    title_re=pat
                )
                if (not dlg.exists(timeout=timeout)): continue
                for btn_title in self.overwrite_btn_titles:
                    try:
                        btn = dlg.child_window(title=btn_title, class_name=self.btn_classname)
                        if (btn.exists(timeout=timeout)):
                            btn.click()
                            return
                    except Exception:
                        pass
            except Exception:
                pass


def default_retry_save_edit(edit: DialogControl, expected: str, options: RetryOptions | None=None):
    if (not options):
        options = RetryOptions()
    attempt: int = 0
    while (attempt < options.max_attempts):
        edit.set_focus()
        edit.type_keys("^a{BACKSPACE}", set_foreground=True)
        edit.type_keys(expected, with_spaces=True, set_foreground=True)
        time.sleep(0.1)
        actual = str(edit.window_text())
        if (actual == expected): return True
        attempt += 1
    return False
