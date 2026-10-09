"""
*`@file`* `gui/services/_export/windows_save`
- after ExportOptions.invoke, when get windows native dialog instead of sapgui dialog
"""
from __future__ import annotations

from dataclasses import dataclass, field as _field
import time
from typing import (Any, Callable, Iterable, Literal)
from pyqi import (require)
from pyqi.models import (RetryOptions, )
from lute import LogMsg, get_logger
from pywinauto import Desktop
from pywinauto.base_wrapper import BaseWrapper
from resin.utils.winauto import (DesktopBackend, 
    ControlOptions, AutomationError, WindowClass, CommonControl
)
mlog = get_logger(__file__, name_depth=2)

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

