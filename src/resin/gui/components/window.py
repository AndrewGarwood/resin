"""
*`@file`* `gui/components/window`
"""
from __future__ import annotations
from .container import (VContainer)
from pyqi import export
from .registry import (register_component)

@register_component()
class FrameWindow(VContainer):
    def send_vkey(self, key: int):
        self._com.SendVKey(key)

    def is_vkey_allowed(self, key: int):
        return bool(self._com.IsVKeyAllowed(key))

    def maximize(self):
        self._com.Maximize()

    def restore(self):
        self._com.Restore()

    def close(self):
        self._com.Close()

    @property
    def handle(self) -> int:
        return self.gateway.get_property(self._com, "Handle", int, _raise=True)


@register_component()
class MainWindow(FrameWindow):
    def resize_working_pane(
        self,
        width_chars: int,
        height_chars: int,
        _raise: bool = False,
    ):
        self._com.ResizeWorkingPane(width_chars, height_chars, _raise)
        return self

@register_component()
class ModalWindow(FrameWindow):
    ...

__all__ = export(FrameWindow, MainWindow, ModalWindow)
