"""
*`@file`* `gui/components/status_bar`
"""
from __future__ import annotations
from typing import Literal
from pyqi import String, export
from json import dumps as json_dumps
from .component import (Component)
from .registry import (register_component)

@register_component()
class Statusbar(Component):
    """
    [GuiStatusbar](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/d3fcc9198de14195bf2237d22dbcafad.html)
    """
    @property
    def message_type(self) -> Literal["S", "W", "E", "A", "I"] | str:
        return self._gateway.get_property(
            self._resolve(), 
            "MessageType",
            default="<unknown>",
        )

    @property
    def message_id(self) -> str:
        return self._gateway.get_property(
            self._resolve(),
            "MessageId",
            str,
            default="<unknown>",
        )

    @property
    def message_number(self) -> str:
        """ 
        "the name of the message number used in the ABAP message call. It will usually be a number, but this is not enforced by the system."
        """
        return self._gateway.get_property(
            self._resolve(),
            "MessageNumber",
            str, 
            default="<unknown>",
        )

    @property
    def has_popup(self) -> bool:
        result = self._gateway.get_property(
            self._resolve(), 
            "MessageAsPopup", 
            bool
        )
        return (result if result is not None else False)
    @property
    def is_error(self) -> bool:
        return self.message_type == StatusMessageType.ERROR.value

    @property
    def is_warning(self) -> bool:
        return self.message_type == StatusMessageType.WARNING.value

    @property
    def is_success(self) -> bool:
        return self.message_type == StatusMessageType.SUCCESS.value

    def open_long_text(self):
        self._resolve().DoubleClick()

    @property
    def handle(self) -> int:
        return self.gateway.get_property(self._resolve(), "Handle", int, _raise=True)

    @property
    def has_long_text(self) -> bool:
        value: Literal[1, 0, -1] = self._gateway.get_property(
            self._resolve(), "MessageHasLongText", _raise=True
        )
        return isinstance(value, int) and value == 1

    @property
    def status(self) -> str:
        return self.get_status(
            "text", 
            "message_id",
            "message_type", 
            "message_number"
        )
    def get_status(
        self, 
        *props: str,
        indent: int=4
    ) -> str:
        """ 
        *`@param`* `props` - properties of `self`, not the 'self._resolve()' com object 
        - TODO: allow + handle props of the GuiStatusbar com object
        """
        kwargs = { 
            k: getattr(self, k, "<unknown>") 
            for k in props
        }
        return f"[session(id={self.id}).status()] {json_dumps(kwargs, indent=indent)}"

class StatusMessageType(String.BaseEnum):
    ERROR = "E"
    SUCCESS = "S"
    WARNING = "W"
    ABORT = "A"
    INFORMATION = "I"


__all__ = export(Statusbar, StatusMessageType)