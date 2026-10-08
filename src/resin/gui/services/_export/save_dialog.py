"""
*`@file`* `gui/services/_export/save_dialog`
"""
from __future__ import annotations

from dataclasses import dataclass, field as _field
import time
from pathlib import Path
from typing import (Any, Callable, Iterable, Literal, Sequence, TypeAlias, TypedDict)
from pyqi import (Array, export, require)
from pyqi.models import (RetryOptions, RetryOptionsDict)
from lute import LogMsg, get_logger
from pywinauto import Desktop
from pywinauto.base_wrapper import BaseWrapper
from resin.utils.winauto.watcher import (NativeDialogWatcher)
from resin.utils.winauto import (DesktopBackend, 
    Win32Window, ControlOptions, AutomationError, WindowClass, CommonControl
)
from .constants import (
    OVERWRITE_CONFIRM_BUTTON_TITLES, 
    OVERWRITE_DIALOG_TITLE_PATTERNS, 
    SAVE_BUTTON_PATTERNS,
    SAVE_DIALOG_TITLE_PATTERN
)

mlog = get_logger(__file__, name_depth=2)

def default_dialog_selector(candidates: Iterable[BaseWrapper], /,) -> BaseWrapper:
    return max(candidates, key=lambda c: c.rectangle().width())

DEFAULT_SAVE_DIALOG_OPTIONS = ControlOptions(
    class_name=WindowClass.DIALOG,
    title_re=SAVE_DIALOG_TITLE_PATTERN
)

DEFAULT_SAVE_EDIT_OPTIONS = ControlOptions(
    class_name=CommonControl.EDIT
)
DEFAULT_SAVE_BUTTON_OPTIONS = ControlOptions(
    class_name=CommonControl.BUTTON,
    title_re=SAVE_BUTTON_PATTERNS
)
DEFAULT_OVERWRITE_DIALOG_OPTIONS = ControlOptions(
    class_name=WindowClass.DIALOG,
    title_re=OVERWRITE_DIALOG_TITLE_PATTERNS
)
DEFAULT_OVERWRITE_CONFIRM_BUTTON_OPTIONS = ControlOptions(
    class_name=CommonControl.BUTTON,
    title=OVERWRITE_CONFIRM_BUTTON_TITLES
)

@dataclass
class NativeSaveDialogOptions:
    save_dialog: ControlOptions = _field(default=DEFAULT_SAVE_DIALOG_OPTIONS)
    save_edit_selector: Callable[[Iterable[Any]], Any] = _field(default=default_dialog_selector)
    save_edit: ControlOptions = _field(default=DEFAULT_SAVE_EDIT_OPTIONS)
    save_btn: ControlOptions = _field(default=DEFAULT_SAVE_BUTTON_OPTIONS)
    overwrite_dialog: ControlOptions = _field(default=DEFAULT_OVERWRITE_DIALOG_OPTIONS)
    overwrite_btn: ControlOptions = _field(default=DEFAULT_OVERWRITE_CONFIRM_BUTTON_OPTIONS)
    retry: RetryOptions = _field(default_factory=RetryOptions)
    backend: DesktopBackend = DesktopBackend.WIN32


def handle_overwrite(
    backend: DesktopBackend, 
    dlg_ctrl: ControlOptions, 
    btn_ctrl: ControlOptions, 
    *, 
    timeout: float=5.0
):
    desktop = Desktop(backend=backend)
    for pat in dlg_ctrl._title_patterns:
        try:
            dlg = desktop.window(
                class_name=dlg_ctrl.class_name, title_re=pat
            )
            if (not dlg.exists(timeout=timeout)): continue
            for btn_title in btn_ctrl._titles:
                try:
                    btn = dlg.child_window(
                        title=btn_title, 
                        class_name=btn_ctrl.class_name
                    )
                    if (btn.exists(timeout=timeout)):
                        btn.click()
                except Exception:
                    pass
        except Exception:
            pass
    return None


def handle_save_edit(
    edit: Any, 
    expected: str, 
    retry: RetryOptions
):
    actual = _set_edit_text(edit, expected, how='setter')
    attempt: int = 1
    while (actual != expected and attempt <= retry.max_attempts):
        _set_edit_text(edit, expected, how='type')
        time.sleep(0.1)
        actual = str(edit.window_text())
        attempt += 1
    if (actual != expected and attempt >= retry.max_attempts):
        raise AutomationError(LogMsg(
            f"Failed to set save edit text to expected value after {attempt} attempt(s)",
        ))
    return None


def _set_edit_text(
    edit: Any, 
    /, 
    value: str, 
    *, 
    how: Literal['type', 'setter'], 
    sleep_seconds: float=0.1
):
    edit.set_focus()
    if (sleep_seconds is not None and int(sleep_seconds) != 0):
        sleep_seconds = require.positive_number(sleep_seconds)
    if (how == 'type'):
        edit.type_keys("^a{BACKSPACE}", set_foreground=True)
        edit.type_keys(value, with_spaces=True, set_foreground=True)
    elif (how == 'setter'):
        edit.set_edit_text(value)
    else:
        raise ValueError(LogMsg.bad_arg(
            how, "_set_edit_text.how", "Unsupported value", "Literal['type', 'setter']"
        ))
    time.sleep(sleep_seconds or 0.1)
    return str(edit.window_text())

