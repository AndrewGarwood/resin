"""
*`@file`* `gui/components/control`
"""
from __future__ import annotations
from typing import Any

from .component import (Component, VComponent)
from .registry import (register_component)
from ..utils.concurrency import (busy_safe)
from ..utils.debug import (debug_component)
from lute import LogMsg
from pyqi import export
from ..exceptions import (SapComError)

@register_component()
class CheckBox(VComponent):
    """
    - [SAP GuiCheckBox](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/60579254b8914b699dd2c681e8eb1b79.html) 
    """
    @property
    def selected(self) -> bool:
        """ 
        Like radio buttons, checking a checkbox can cause server communication, 
        depending on ABAP Screen Painter definition. 
        """
        return self._gateway.get_property(
            self._resolve(), "Selected", bool, 
            _raise=True,
            source=self.__class__.__name__
        )
    @selected.setter
    def selected(self, value: bool):
        self._resolve().Selected = value
    
    @busy_safe()
    def set(self, value: bool, /):
        self._resolve().Selected = value
        return self.session

@register_component()
class TextField(VComponent):
    @property
    def text(self) -> str:
        return self._com.Text
    @text.setter
    def text(self, value: str) -> None:
        self.set(value)

    def get(self) -> str:
        return self._com.Text
    
    @busy_safe()
    def set(self, value: str, /):
        obj = self._resolve()
        value = "" if value is None else str(value)
        changeable = self._gateway.get_property(
            obj, 
            "Changeable", 
            default=None, 
            _raise=False, 
        )
        current_text = self._gateway.get_property(
            obj, "Text", str, _raise=False
        )
        try:
            if (not changeable):
                if str(current_text) == value:
                    return self.session
                raise SapComError(f"Field is not changeable")
            try:
                obj.SetFocus()
            except Exception as e:
                print(f" > unable to set focus: {e}")
                pass
            obj.Text = value
        except Exception as e:
            raise SapComError(LogMsg.err(e,
                f"Failed to set value of text field."
                f"attempted_value={value!r}",
                f"diagnostics:", 
                *debug_component(obj)
            )) from e
        return self.session

    def clear(self):
        self.set("")
        return self

@register_component()
class CTextField(TextField):
    """ 
    `'combo text field' ?` (has combo box button when cursor set into a text field)  
    """
    ...


@register_component()
class Label(VComponent):
    def get_list_property(self, prop: str, /) -> str:
        return self._resolve().GetListProperty(prop)
    
@register_component()
class Button(Component):
    def press(self): 
        self._resolve().Press()
        return self.session

@register_component()
class RadioButton(VComponent):
    @busy_safe()
    def select(self):
        self._resolve().Select()

    @property
    def group_members(self) -> Any:
        return self._gateway.get_property(
            self._resolve(), "GroupMembers", _raise=True
        )
    @property
    def group_count(self) -> int:
        return self._gateway.get_property(
            self._resolve(), "GroupCount", int, _raise=True
        )

__all__ = export(CheckBox, RadioButton, TextField, CTextField, Label, Button)