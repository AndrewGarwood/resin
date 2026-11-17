"""
*`@file`* `gui/services/_export/watcher`
"""

from dataclasses import dataclass
import time, re
import win32gui
from pathlib import Path
from contextlib import contextmanager
from typing import (Any, Iterable)
from pyqi import (Array, LockManager, require, Function, fs)
from pyqi.models import RetryOptions
from lute import LogMsg, get_logger, annotate
from threading import (Event, Thread)
from resin.utils.runtime import com_apartment
from pywinauto import Desktop
from pywinauto.base_wrapper import BaseWrapper
from resin.utils.winauto.watcher import (NativeDialogWatcher)
from resin.utils import winauto
from resin.utils.winauto import (
    inspect_descendants, 
    AutomationError, 
    control_is_available, 
    DesktopBackend, 
    window,
    is_owned_by, 
    iter_owner_chain,
    find_window_by_title
)
from .constants import (NATIVE_SAVE_DIALOG_POLL, NATIVE_SAVE_DIALOG_TIMEOUT)
from .locks import NATIVE_DIALOG_HANDLE_LM
from .types import (NativeSaveDialogOptions)
from .windows_save import (handle_overwrite, handle_save_edit)

mlog = get_logger(__file__, name_depth=1)


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
        owner_hwnd=owner_hwnd,
        timeout=timeout, 
        poll=poll
    )
    watcher.thread = Thread(
        target=worker, 
        name=f"NativeSaveDialogWatcher({owner_hwnd=})", 
        daemon=True
    )
    watcher.thread.start()
    return watcher


def _save_worker(
    watcher: NativeSaveDialogWatcher,
    options: NativeSaveDialogOptions,
    outpath: Path,
    cancel: Event,
    done: Event,
    *,
    owner_hwnd: int | None = None,
    timeout: float = 30.0,
    poll: float = 0.15,
) -> None:
    claimed_handle: int | None = None

    try:
        with com_apartment():
            deadline = time.monotonic() + timeout
            desktop = Desktop(backend=str(options.backend))

            if owner_hwnd is not None:
                mlog.debug(LogMsg(
                    "Native save watcher started",
                    owner=winauto.describe_window(owner_hwnd),
                    timeout=timeout,
                    poll=poll,
                ))

            while (
                not cancel.is_set()
                and time.monotonic() < deadline
            ):
                wrapper = _find_save_dialog(
                    desktop,
                    options,
                    owner_hwnd=owner_hwnd,
                )

                if wrapper is None:
                    cancel.wait(poll)
                    continue

                handle = int(wrapper.handle)

                mlog.debug(
                    LogMsg(
                        "Native save dialog candidate detected",
                        dialog=winauto.describe_window(handle),
                        expected_owner_hwnd=owner_hwnd,
                    )
                )

                if not NATIVE_DIALOG_HANDLE_LM.claim_handle(handle):
                    cancel.wait(poll)
                    continue

                claimed_handle = handle

                try:
                    if not win32gui.IsWindow(handle):
                        continue

                    if not control_is_available(wrapper):
                        continue

                    if (
                        owner_hwnd is not None
                        and not is_owned_by(handle, owner_hwnd)
                    ):
                        continue

                    watcher.handle_dialog(
                        wrapper,
                        options,
                        outpath,
                    )
                    return
                finally:
                    NATIVE_DIALOG_HANDLE_LM.release_handle(handle)
                    claimed_handle = None

            if cancel.is_set():
                mlog.debug(
                    "Native save dialog watcher was cancelled"
                )
                return

            watcher.timed_out = True
            watcher.error = TimeoutError(
                f"No eligible native save dialog was detected "
                f"within {timeout:.1f} seconds"
            )

    except BaseException as e:
        watcher.error = e

        mlog.exception(
            LogMsg.err(
                e,
                "Native save dialog watcher failed",
                owner_hwnd=owner_hwnd,
                outpath=str(outpath),
            )
        )

    finally:
        if claimed_handle is not None:
            NATIVE_DIALOG_HANDLE_LM.release_handle(
                claimed_handle
            )

        done.set()
# def _save_worker(
#     watcher: NativeSaveDialogWatcher,
#     options: NativeSaveDialogOptions, 
#     outpath: Path, 
#     cancel: Event,
#     done: Event,
#     *, 
#     owner_hwnd: int | None=None,
#     timeout: float=30.0, 
#     poll: float=0.15
# ):
#     with com_apartment():
#         claimed_handle: int | None = None
#         if (owner_hwnd is not None):
#             mlog.debug(LogMsg(
#                 "_save_worker describing owner hwnd:", 
#                 winauto.describe_window(owner_hwnd)
#             ))
            
#         try:
#             deadline = time.monotonic() + timeout
#             desktop = Desktop(backend=str(options.backend))
#             while (
#                 not cancel.is_set() 
#                 and time.monotonic() < deadline
#             ):
#                 # wrapper = _find_save_dialog(desktop, options, owner_hwnd=owner_hwnd)
#                 candidate = desktop.window(
#                     class_name=options.save_dialog.class_name, 
#                     title_re=options.save_dialog.title_re
#                 )
#                 if candidate is None or not candidate.exists(timeout=2.0):
#                     cancel.wait(poll)
#                     continue
#                 wrapper = candidate.wrapper_object()
#                 handle = int(wrapper.handle)
#                 mlog.debug(LogMsg(
#                     "Native save dialog candidate detected",
#                     dialog=winauto.describe_window(handle),
#                     expected_owner_hwnd=owner_hwnd,
#                 ))
#                 if (not NATIVE_DIALOG_HANDLE_LM.claim_handle(handle)):
#                     cancel.wait(poll)
#                     continue
#                 claimed_handle = handle
#                 try:
#                     if (not win32gui.IsWindow(handle)): continue
#                     if (not control_is_available(wrapper)): continue
#                     if (owner_hwnd is not None and not is_owned_by(handle, owner_hwnd)):
#                         continue
#                     watcher.handle_dialog(wrapper, options, outpath)
#                 finally:
#                     NATIVE_DIALOG_HANDLE_LM.release_handle(handle)
#                     claimed_handle = None
#             if cancel.is_set():
#                 mlog.debug(LogMsg("Native save dialog watcher was cancelled"))
#                 return
#             watcher.timed_out = True
#             watcher.error = TimeoutError(
#                 f"No eligible native save dialog was detected "
#                 f"within {timeout:.1f} seconds"
#             )

#         except BaseException as e:
#             watcher.error = e
#             mlog.exception(LogMsg.err(
#                 e,
#                 "Native save dialog watcher failed",
#                 owner_hwnd=owner_hwnd,
#                 outpath=str(outpath),
#             ))
#         finally:
#             if claimed_handle is not None:
#                 try:
#                     NATIVE_DIALOG_HANDLE_LM.release_handle(
#                         claimed_handle
#                     )
#                 except Exception:
#                     mlog.exception(
#                         "Failed to release native dialog handle"
#                     )

#             # Wake every waiter, regardless of success, failure, or timeout.
#             watcher.handled_event.set()
#             done.set()

@contextmanager
def native_save_dialog_watcher(
    options: NativeSaveDialogOptions, 
    outpath: str | Path, 
    owner_hwnd: int,
    timeout: float = NATIVE_SAVE_DIALOG_TIMEOUT,
    poll: float = NATIVE_SAVE_DIALOG_POLL, 
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
        if watcher.thread is not None:
            watcher.thread.join(timeout=3.0)

            if watcher.thread.is_alive():
                mlog.error(LogMsg(
                    "Native save dialog watcher thread is still alive",
                    thread_name=watcher.thread.name,
                ))
        if not watcher.wait_done(timeout=3.0):
            mlog.error(LogMsg(
                "Native save dialog watcher did not stop",
                thread_name=(
                    watcher.thread.name
                    if watcher.thread is not None
                    else None
                ),
                thread_alive=(
                    watcher.thread.is_alive()
                    if watcher.thread is not None
                    else None
                ),
            ))


def _find_save_dialog(
    desktop: Desktop,
    options: NativeSaveDialogOptions,
    *,
    owner_hwnd: int | None,
    excluded_handles: Iterable[int] = (),
) -> BaseWrapper | None:
    """  
    collect all eligible candidates, validate the HWND, owner chain, visibility, and enabled state, 
    then choose the newest or most foreground-relevant candidate.
    """
    class_name = str(options.save_dialog.class_name)
    title_pattern = re.compile(str(options.save_dialog.title_re))
    excluded = set(excluded_handles)

    candidates: list[BaseWrapper] = []

    for candidate in desktop.windows(
        class_name=class_name,
        visible_only=True,
        enabled_only=True,
    ):
        try:
            handle = int(candidate.handle)

            if handle in excluded:
                continue

            if not win32gui.IsWindow(handle):
                continue

            if not control_is_available(candidate):
                continue

            title = candidate.window_text()

            if title_pattern.fullmatch(title) is None:
                continue

            if (
                owner_hwnd is not None
                and not is_owned_by(handle, owner_hwnd)
            ):
                continue

            candidates.append(candidate)

        except Exception as e:
            mlog.debug(LogMsg.err(
                e,
                "Rejected native dialog candidate",
                handle=getattr(candidate, "handle", None),
            ))

    if not candidates:
        return None

    foreground_hwnd = win32gui.GetForegroundWindow()

    candidates.sort(
        key=lambda candidate: (
            int(candidate.handle) == foreground_hwnd,
            candidate.rectangle().width() * candidate.rectangle().height(),
        ),
        reverse=True,
    )

    return candidates[0]

# def _find_save_dialog(
#     desktop: Desktop,
#     options: NativeSaveDialogOptions,
#     *,
#     owner_hwnd: int | None,
# ) -> BaseWrapper | None:
#     class_name = str(options.save_dialog.class_name)
#     title_pattern = re.compile(options.save_dialog.title_re)
#     for i, window in enumerate(desktop.windows(
#         class_name=class_name,
#         visible_only=True,
#     )):
#         mlog.debug(LogMsg(f"_find_save_dialog @ window {i=}"))
#         winauto.describe_window(window)

#         if (not control_is_available(window)):
#             continue

#         if not title_pattern.match(window.window_text()):
#             continue
#         handle = int(window.handle)
#         if (owner_hwnd is not None
#             and not is_owned_by(handle, owner_hwnd)
#         ):
#             continue
#         return window
#     return None
