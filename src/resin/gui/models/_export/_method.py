"""
*`@file`* `gui/models/_export/method`
"""
from typing import (Self, TypedDict, Any, )
from pyqi import (String, Json, export, guard)
from lute import LogMsg
from resin.gui.utils import gui_id as GUI

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
    button_id: str
    vkey: int
    grid_id: str
    menu_item_id: str
    menu_item_position: str
    menu_element_class: str

class InvokeMethodOptions(Json.Serial[InvokeMethodOptionsDict]):
    """
    ```
    button_id: str | None = None # method = 'toolbar_button'
    vkey: int | None = None # method = 'keyboard_shortcut'
    grid_id: str | None = None # method = 'context_menu'
    menu_item_id: str | None = None # method = 'context_menu'
    menu_item_position: str | None = None # method = 'context_menu' # less robust alternative to menu_item_id
    ```
    """
    button_id: str | None = None
    vkey: int | None = None
    grid_id: str | None = None
    menu_item_id: str | None = None
    menu_item_position: str | None = None
    menu_element_class: str | None = None

    def __init__(self,
        button_id: str | None = None,
        vkey: int | None = None,
        grid_id: str | None = None,
        menu_item_id: str | None = None,
        menu_item_position: str | None = None,
        menu_element_class: str | None = None,
    ):
        self.button_id = button_id
        self.vkey = vkey
        self.grid_id = grid_id
        self.menu_item_id = menu_item_id
        self.menu_item_position = menu_item_position
        self.menu_element_class = menu_element_class

    @classmethod
    def from_dict(
        cls, 
        data: InvokeMethodOptionsDict | dict[str, Any] | str | int, 
        /,
    ) -> Self:
        """
        *`@param`* `data (InvokeMethodOptionsDict | str | int)`
            - `int and >= 0` → `cls(vkey=data)`
            - `str and GUI.field_type(data) == 'btn'` → `cls(button_id=data)`
        """
        try:
            if (isinstance(data, str)):
                if (GUI.field_type(data) == 'btn'):
                    return cls(button_id=data)
                if (data.isdigit()):
                    _candidate_vkey = int(data)
                    if (guard.is_non_negative_integer(_candidate_vkey)):
                        return cls(vkey=_candidate_vkey)
                raise ValueError(LogMsg(
                    f"Unable to construct InvokeMethodOptions from string.",
                    f"string value must be id of a GuiButton component or a VKey integer"
                ))
            if (isinstance(data, int)):
                if (guard.is_non_negative_integer(data)):
                    return cls(vkey=data)
                raise ValueError(LogMsg(
                    f"Unable to construct InvokeMethodOptions from integer.",
                    f"integer value must correspond to valid VKey"
                ))
            return cls(
                button_id=data.get("button_id"),
                vkey=data.get("vkey"),
                grid_id=data.get("grid_id"),
                menu_item_id=data.get("menu_item_id"),
                menu_item_position=data.get("menu_item_position"),
                menu_element_class=data.get("menu_element_class"),
            )
        except (ValueError, KeyError): raise
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                f"Failed to construct InvokeMethodOptions from given value.",
                received=Json.serialize(data)
            )) from e
    

__all__ = export(
    ExportMethod, 
    InvokeMethodOptionsDict, 
    InvokeMethodOptions
)