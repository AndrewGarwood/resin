"""
*`@file`* `gui/components/window`
"""
from __future__ import annotations
from .container import (VContainer)
from pyqi import export


class FrameWindow(VContainer):
    def send_vkey(self, key: int):
        self._com.SendVKey(key)
        return self

    def is_vkey_allowed(self, key: int):
        return bool(self._com.IsVKeyAllowed(key))

    def maximize(self):
        self._com.Maximize()
        return self

    def restore(self):
        self._com.Restore()
        return self

    def close(self):
        self._com.Close()
        return self


class MainWindow(FrameWindow):
    def resize_working_pane(
        self,
        width_chars: int,
        height_chars: int,
        _raise: bool = False,
    ):
        self._com.ResizeWorkingPane(width_chars, height_chars, _raise)
        return self

class ModalWindow(FrameWindow):
    ...

__all__ = export(FrameWindow, MainWindow, ModalWindow)
