"""
*`@file`* `gui/components/shell`
- [GuiShell](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/87c4e965ed4e402b982dc399e34526c7.html)
"""

from .container import VContainer
from ..utils.concurrency import busy_safe
from .registry import register_component
from pyqi import (export)

@register_component()
class Shell(VContainer):
    @busy_safe()
    def select_context_menu_item(self, code: str,/):
        """ Select an item from the control's context menu. """
        self._com.SelectContextMenuItem(code)

    @busy_safe()
    def select_context_menu_item_by_position(self, position: str, /):
        self._com.SelectContextMenuItemByPosition(position)
    
    @busy_safe()
    def select_context_menu_item_by_text(self, text: str, /):
        """ Select a menu item of a context menu using the text of the item and possible higher level menus. """
        self._com.SelectContextMenuItemByText(text)
    
    @property
    def handle(self) -> int:
        """ window handle of control that is conencted to GuiShell """
        return self.gateway.get_property(self._com, "Handle", int, _raise=True)
    @property
    def sub_type(self) -> str:
        """ 
        Additional type information to identify the control represented by the shell, for example Picture, TextEdit, GridView… 
        """
        return self.gateway.get_property(self._com, "SubType", str, _raise=True)


__all__ = export(Shell)