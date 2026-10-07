"""
*`@file`* `gui/services/_export/watcher`
"""

from dataclasses import dataclass, field as _field
import time
from pathlib import Path
from typing import (Any, Callable, Iterable, Sequence, TypeAlias)
from pyqi import Array
from pyqi.models import RetryOptions
from lute import LogMsg, get_logger
from pywinauto import Desktop
from pywinauto.base_wrapper import BaseWrapper
from resin.utils.winauto.watcher import (NativeDialogWatcher)
from resin.utils.winauto import (
    inspect_descendants, 
    WindowsAutomationError, 
    control_is_available, DesktopBackend, 
    WindowClass, window
)

mlog = get_logger(__file__, name_depth=2)


DialogControl: TypeAlias = Any

@dataclass
class NativeSaveDialogOptions():
    outpath: Path
    selector: Callable[[Iterable[DialogControl]], DialogControl]
    """ e.g. 
    `def select_largest_edit(edits): return max(edits, key=lambda e: e.rectangle().width()) `
    """
    retry_edit: Callable[[DialogControl, str, RetryOptions | None], bool] | None = None
    backend: DesktopBackend = DesktopBackend.WIN32
    edit_classname: str = "Edit"
    btn_classname: str = "Button"
    save_btn_patterns: list[str] = _field(default_factory=list)
    """
    defaults to 
    `[ r"^.*Save.*$", r"^&Save$", r"^Save$", r"^&Open$", r"^Open$", r"^OK$"]`
    """
    overwrite_window_classname: str = WindowClass.DIALOG.value
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

@dataclass
class NativeSaveDialogWatcher(NativeDialogWatcher[NativeSaveDialogOptions]):
    def handle_dialog(
        self, 
        dlg: BaseWrapper | Any, 
        options: NativeSaveDialogOptions, 
        *args,
        **kwargs
    ):
        options.outpath.parent.mkdir(parents=True, exist_ok=True)
        dlg.set_focus()
        edits: list[BaseWrapper] = Array.filter(
            dlg.descendants(class_name=options.edit_classname), 
            control_is_available
        )
        if (not edits):
            mlog.error(LogMsg(
                f"No valid '{options.edit_classname}' controls found"
            ))
            inspect_descendants(dlg)
            raise WindowsAutomationError(
                f"Unable to fill save dialog. No enabled & visible controls found"
            )
        expected = str(options.outpath)
        edit = options.selector(edits)
        edit.set_focus()
        edit.set_edit_text(expected)
        time.sleep(0.1)
        actual = str(edit.window_text())
        if (options.retry_edit and actual != expected):
            retry_successful = options.retry_edit(edit, expected, None)
            if (not retry_successful):
                raise RuntimeError(LogMsg(
                    f"Failed to set edit text value to outpath string",
                    expected=expected,
                    actual=str(edit.window_text())
                ))
            
        clicked: bool = False
        for btn_pat in options.save_btn_patterns:
            try:
                btns = Array.filter(
                    dlg.descendants(
                        title_re=btn_pat, 
                        class_name=options.btn_classname
                    ), 
                    control_is_available
                )
                if (not btns):
                    raise RuntimeError(f"No available save button found")
                btn = btns[0]
                btn.click_input()
                clicked = True
            except Exception as e:
                mlog.warning(LogMsg.err(e, f"Button lookup failed for title_re={btn_pat!r}"))
        if (not clicked):
            mlog.debug(f"Confirm Save button not found, pressing 'ENTER'")
            dlg.type_keys("{ENTER}")
        self.mark_handled()


