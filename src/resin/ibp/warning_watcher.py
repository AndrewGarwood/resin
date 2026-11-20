"""
*`@file`* `ibp/warning_watcher`
"""
from __future__ import annotations
from contextlib import contextmanager
import sys, time
from typing import Generator, Any
from pyqi import (Function)
from pywinauto.controls.hwndwrapper import (DialogWrapper)
from threading import (Thread, Event)
from pywinauto.base_wrapper import BaseWrapper
from lute import get_logger
from resin.utils.winauto.watcher import (NativeDialogWatcher)
from resin.utils import winauto
from resin.utils.runtime import com_apartment
from .constants import (VERSION_WARNING_WINDOW_TITLE)

mlog = get_logger(__file__, name_depth=1)


class WarningDialogWatcher(NativeDialogWatcher[None, DialogWrapper]):
    def handle_dialog(
        self, 
        dlg: DialogWrapper, 
        /,
    ) -> None:
        dlg.close()
        self.mark_handled()
        return None


@contextmanager
def version_warning_watcher(
    options: winauto.WindowOptionsDict, 
    /,
) -> Generator[WarningDialogWatcher, None, None]:
    """Watch only during Connect; absence of the optional warning is normal."""
    watcher = WarningDialogWatcher(
        cancel=Event(),
        done=Event(),
        handled_event=Event(),
        thread=None,
        backend=None,
    )
    _info = options.get('process', '<pid_unavailable>')
    thread = Thread(
        target=Function.Deferred(
            _warning_worker, 
            watcher, 
            options
        ),
        name=f"IbpVersionWarningWatcher({_info})",
        daemon=True,
    )
    watcher.thread = thread
    thread.start()
    try:
        yield watcher
    finally:
        watcher.stop()
        thread.join(timeout=2.0)
        if thread.is_alive():
            mlog.error("IBP version warning watcher did not stop")
            if sys.exc_info()[0] is None:
                raise RuntimeError("IBP version warning watcher did not stop")
        if watcher.error is not None and sys.exc_info()[0] is None:
            raise RuntimeError(
                "IBP version warning watcher failed"
            ) from watcher.error

def _warning_worker(
    watcher: WarningDialogWatcher, 
    options: winauto.WindowOptionsDict
    ) -> None:
    try:
        with com_apartment():
            while not watcher.cancel.is_set():
                dlg = winauto.find_window(
                    options, 
                    expected_wrapper=DialogWrapper, 
                    strict=False
                )
                if (dlg is None):
                    watcher.cancel.wait(0.15)
                    continue
                watcher.handle_dialog(dlg)
                if watcher.cancel.is_set():
                    return
                watcher.cancel.wait(0.15)
    except Exception as e:
        watcher.error = e
        mlog.exception("IBP version warning watcher failed")
    finally:
        watcher.done.set()
