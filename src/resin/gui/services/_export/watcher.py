"""
*`@file`* `gui/services/_export/watcher`
"""

from dataclasses import dataclass, field as _field
import time
from pathlib import Path
from contextlib import contextmanager
from typing import (Any, Callable, Iterable, Sequence, TypeAlias, TypedDict)
from pyqi import (Array, LockManager, require, Function, fs)
from pyqi.models import RetryOptions
from lute import LogMsg, get_logger, annotate
from threading import (Event, Thread)
from resin.utils.runtime import com_apartment
from pywinauto import Desktop
from pywinauto.base_wrapper import BaseWrapper
from resin.utils.winauto.control.types import ControlState
from resin.utils.winauto.watcher import (NativeDialogWatcher)
from resin.utils.winauto import (
    inspect_descendants, 
    AutomationError, 
    control_is_available, DesktopBackend, 
    WindowClass, window,
)
from .locks import NATIVE_DIALOG_HANDLE_LM
from .types import (NativeSaveDialogOptions)
from .windows_save import (handle_overwrite, handle_save_edit)

mlog = get_logger(__file__, name_depth=2)


@dataclass
class NativeSaveDialogWatcher(NativeDialogWatcher[NativeSaveDialogOptions]):
    def handle_dialog(
        self, 
        dlg: BaseWrapper | Any, 
        options: NativeSaveDialogOptions,
        outpath: Path
    ):
        try:
            outpath.parent.mkdir(parents=True, exist_ok=True)

            dlg.set_focus()
            edits: list[BaseWrapper] = Array.filter(
                dlg.descendants(class_name=options.save_edit.class_name), 
                control_is_available
            )
            if (not edits):
                mlog.error(LogMsg(
                    f"No valid '{options.save_edit.class_name}' controls found"
                ))
                inspect_descendants(dlg)
                raise AutomationError(
                    f"Unable to fill save dialog. No enabled & visible controls found"
                )
            edit = options.save_edit_selector(edits)
            handle_save_edit(
                edit, 
                str(outpath), 
                options.retry or RetryOptions()
            )
            time.sleep(0.1)
            clicked: bool = False
            pat = options.save_btn.title_re
            try:
                btns = Array.filter(
                    dlg.descendants(
                        title_re=pat,
                        class_name=options.save_btn.class_name
                    ),
                    control_is_available
                )
                if (not btns):
                    raise RuntimeError(f"No available save button found")
                btn = btns[0]
                btn.click_input()
                clicked = True
            except Exception as e:
                mlog.warning(LogMsg.err(
                    e, 
                    f"Failed to find and click save button",
                    pattern=str(pat)
                ))
            if (not clicked):
                mlog.debug(f"Confirm Save button not found, pressing 'ENTER'")
                dlg.type_keys("{ENTER}")
            time.sleep(0.1)
            handle_overwrite(
                options.backend, 
                options.overwrite_dialog, 
                options.overwrite_btn
            )
            self.mark_handled()
            time.sleep(1.0)
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e,
                f"Failed to handle save dialog.",
                dlg=annotate(dlg),
                options=str(options),
                outpath=str(outpath)
            )) from e



def start_watcher(
    options: NativeSaveDialogOptions, 
    outpath: Path, 
    *, 
    owner_hwnd: int | None=None,
    timeout: float=30.0, 
    poll: float=0.15
): 
    cancel = Event()
    done = Event()
    handled_event = Event()
    watcher = NativeSaveDialogWatcher(
        cancel=cancel, 
        done=done, 
        handled_event=handled_event, 
        thread=None, 
        backend=options.backend
    )
    worker = Function.Deferred(
        _save_worker, 
        options=options, 
        outpath=outpath, 
        watcher=watcher, 
        cancel=cancel, 
        done=done, 
        timeout=timeout, 
        poll=poll
    )
    watcher.thread = Thread(target=worker, name=f"NativeSaveDialogWatcher({owner_hwnd=})", daemon=True)
    watcher.thread.start()
    return watcher



def _save_worker(
    watcher: NativeSaveDialogWatcher,
    options: NativeSaveDialogOptions, 
    outpath: Path, 
    cancel: Event,
    done: Event,
    *, 
    timeout: float=30.0, 
    poll: float=0.15
):
    with com_apartment():
        try:
            deadline = time.monotonic() + timeout
            desktop = Desktop(backend=options.backend)
            while (not cancel.is_set() and time.monotonic() < deadline):
                try:
                    dlg = desktop.window(
                        class_name=options.save_dialog.class_name, 
                        title_re=options.save_dialog.title_re
                    )
                    if (dlg.exists(timeout=2.0)):
                        wrapper = dlg.wrapper_object()
                        handle = int(wrapper.handle)
                        if (not NATIVE_DIALOG_HANDLE_LM.claim_handle(handle)):
                            time.sleep(poll)
                            continue
                        try:
                            # window.dump_class(
                            #     backend=options.backend, 
                            #     class_name=options.save_dialog.class_name
                            # )
                            dlg.wait(ControlState.VISIBLE_ENABLED.value, timeout=3.0)
                            watcher.handle_dialog(dlg, options, outpath)
                            return
                        finally:
                            NATIVE_DIALOG_HANDLE_LM.release_handle(handle)
                except Exception as e:
                    mlog.warning(LogMsg.err(
                        e, 
                        "save worker encountered error while watching for dialog"
                    ))
                time.sleep(poll)
            watcher.timed_out = True
        except BaseException as e:
            mlog.warning(LogMsg.err(e))
        finally:
            done.set()

@contextmanager
def native_save_dialog_watcher(
    options: NativeSaveDialogOptions, 
    outpath: str | Path, 
    owner_hwnd: int,
    timeout: float = 30.0,
    poll: float = 0.15, 
):
    watcher = start_watcher(
        options, 
        fs.to_path(outpath), 
        owner_hwnd=owner_hwnd, 
        timeout=require.positive_number(timeout), 
        poll=require.positive_number(poll)
    )
    try:
        yield watcher
    except Exception as e:
        raise RuntimeError(LogMsg.err(e, outpath=str(outpath))) from e
    finally:
        watcher.stop()
        watcher.wait_done(timeout=3.0)