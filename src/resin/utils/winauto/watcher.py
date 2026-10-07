"""
*`@file`* `utils/winauto/watcher`
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import (Any, Optional, Generic, TypeVar)
from dataclasses import dataclass
from pywinauto.base_wrapper import BaseWrapper
from threading import Event, Thread
from .types import DesktopBackend
from pyqi import export
import lute
LogMsg = lute.LogMsg
mlog = lute.get_logger(__file__, name_depth=1)

T = TypeVar("T")

@dataclass
class NativeDialogWatcher(ABC, Generic[T]):
    cancel: Event
    done: Event
    handled_event: Event
    thread: Optional[Thread]
    # _outpath: Optional[Path]=None # mb remove b/c this is specific to file save dialog
    handled: bool = False
    timed_out: bool = False
    error: Optional[BaseException] = None
    backend: DesktopBackend = DesktopBackend.WIN32
    
    # @property
    # def outpath(self) -> Path:
    #     if (not self._outpath):
    #         raise RuntimeError(f"self._outpath is undefined/empty")
    #     return self._outpath

    def mark_handled(self) -> None:
        self.handled = True
        self.handled_event.set()

    def wait_handled(self, timeout: Optional[float] = None) -> bool:
        self.handled_event.wait(timeout)
        return self.handled

    def wait_done(self, timeout: Optional[float] = None) -> bool:
        self.done.wait(timeout)
        return self.done.is_set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        self.done.wait(timeout)
        return self.handled

    def stop(self) -> None:
        self.cancel.set()

    @abstractmethod
    def handle_dialog(self, dlg: BaseWrapper | Any, options: T, *args, **kwargs): ... # , class_name: FlexStr[WindowClass] = "Edit"


__all__ = export(NativeDialogWatcher)