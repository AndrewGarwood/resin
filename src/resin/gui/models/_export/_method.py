"""
*`@file`* `gui/models/_export/method`
"""
from dataclasses import dataclass
from typing import (Self, TypedDict, Any, )
from pyqi import (String, Json, export)
from lute import LogMsg

class ExportMethod(String.BaseEnum):
    """
    ```
    NONE = "none"
    CONTEXT_MENU = "context_menu"
    TOOLBAR_BUTTON = "toolbar_button"
    KEYBOARD_SHORTCUT = "keyboard_shortcut"
    ```
    """
    NONE = "none"
    """ → do not export the Transaction data"""
    CONTEXT_MENU = "context_menu"
    TOOLBAR_BUTTON = "toolbar_button"
    KEYBOARD_SHORTCUT = "keyboard_shortcut"
    """ e.g. `SendVKey(16)` """
    # TOOLBAR_CONTEXT = "toolbar_context"
    """ ***not implemented/supported*** """

class InvokeMethodOptionsDict(TypedDict, total=False):
    export_button_id: str
    shortcut_vkey: int
    grid_id: str
    menu_item_id: str
    menu_item_position: str
    menu_element_class: str

@dataclass
class InvokeMethodOptions(Json.Serial[InvokeMethodOptionsDict]):
    """
    ```
    export_button_id: str | None = None # method = 'toolbar_button'
    shortcut_vkey: int | None = None # method = 'keyboard_shortcut'
    grid_id: str | None = None # method = 'context_menu'
    menu_item_id: str | None = None # method = 'context_menu'
    menu_item_position: str | None = None # method = 'context_menu' # less robust alternative to menu_item_id
    ```
    """
    export_button_id: str | None = None
    vkey: int | None = None
    grid_id: str | None = None
    menu_item_id: str | None = None
    menu_item_position: str | None = None
    menu_element_class: str | None = None

    @classmethod
    def from_dict(cls, data: InvokeMethodOptionsDict | dict[str, Any]) -> Self:
        try:
            return cls(
                export_button_id=data.get("export_button_id"),
                vkey=data.get("shortcut_vkey"),
                grid_id=data.get("grid_id"),
                menu_item_id=data.get("menu_item_id"),
                menu_item_position=data.get("menu_item_position"),
                menu_element_class=data.get("menu_element_class"),
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(e, received=Json.serialize(data))) from e

__all__ = export(ExportMethod, InvokeMethodOptionsDict, InvokeMethodOptions)