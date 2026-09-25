"""
*`@file`* `gui/utils/id_factory`
"""
from typing import Optional, Final
from pyqi import (BaseIntEnum, BaseStrEnum)


WINDOW_MAIN: Final[int] = 0
WINDOW_MODAL: Final[int] = 1
EXCEL_EXPORT_FUNCTION_CODE = "&XXL"
""" Context Menu Item """
EXPAND_GRID_TOOLBAR_BTN_ID = "&NAVIGATION_PROFILE_TOOLBAR_EXPAND"
EXPORT_TOOLBAR_CONTEXT_BTN_ID = "&MB_EXPORT"
CHOOSE_LAYOUT_GRID_NAME_COLUMN = "VARIANT"

def join(*parts: str) -> str:
    """ *`@returns`* `'/'.join(parts)` """
    return '/'.join(parts)

def wnd(index: int = 0, /) -> str:
    """ `Window i` → `'wnd[i]'` """
    return f"wnd[{index}]"


def tbar(window_index: int = 0, toolbar_index: int = 0, /) -> str:
    """ Toolbar; `'wnd[window_index]/tbar[toolbar_index]'` """
    return f"{wnd(window_index)}/tbar[{toolbar_index}]"

def sbar(window_index: int=0, /) -> str:
    """ StatusBar → `'wnd[0]/sbar'` """
    return f"{wnd(window_index)}/sbar"

def usr(window_index: int = 0, /) -> str:
    """  `GuiUserArea` e.g. `"wnd[0]/usr"` """
    return f"{wnd(window_index)}/usr"

def chk(container_id: str, field_id: str, /) -> str:
    return f"{container_id}/chk{field_id}"

def shell(container_id: str, /) -> str:
    """ *`@returns`* `f"{container_id}/shell"` """
    return f"{container_id}/shell"


def tbar_btn(window_index: int, toolbar_index: int, button_index: int) -> str:
    """ button """
    return f"{tbar(window_index, toolbar_index)}/btn[{button_index}]"


def ctxt(container_id: str, field_id: str, /) -> str:
    """ 
    `GuiCTextField`
    ```
    # field id for export directory and filename:
    ctxt(usr(1), "DY_PATH")   # "wnd[1]/usr/ctxtDY_PATH"
    ctxt(usr(1), "DY_FILENAME")   # "wnd[1]/usr/ctxtDY_FILENAME"
    ```
    """
    return f"{container_id}/ctxt{field_id}"

def txt(container_id: str, field_id: str, /) -> str:
    return f"{container_id}/txt{field_id}"

def lbl(container_id: str, row: Optional[int]=None, col: Optional[int]=None) -> str:
    result = join(container_id, "lbl")
    if (isinstance(row, int) and isinstance(col, int)):
        result += f"[{row},{col}]"
    return result


def okcd(window_index: int = 0, /) -> str:
    """ 
    `okcd` (command field input box)
    e.g. `"wnd[0]/tbar[0]/okcd"`
    """
    return f"{tbar(window_index, 0)}/okcd"

def lowerbound(field_id: str, /) -> str:
    """ *`@returns`* `f"{field_id}-LOW"` """
    return f"{field_id}-LOW"

def upperbound(field_id: str, /) -> str:
    """ *`@returns`* `f"{field_id}-HIGH"` """
    return f"{field_id}-HIGH"

def stem(id: str, /) -> str:
    """ *`@returns`* `id.rsplit("/", 1)[1]` """
    return id.rsplit("/", 1)[1]

def parent(id: str, /) -> str:
    return id.rsplit("/", 1)[0]

def replace_stem(id: str, new_stem: str, /):
    return join(parent(id), new_stem)

def txn_variant_name(window_index: int=1) -> str:
    return txt(usr(window_index), lowerbound(BaseField.txn_variant_name.value))

def txn_variant_created_by(window_index: int=1) -> str:
    return txt(usr(window_index), lowerbound(BaseField.txn_variant_created_by.value))

def txn_variant_fields(window_index: int=1) -> tuple[str, str]:
    """
    *`@returns`* `(variant_name_field_id, variant_created_by_field_id)`
    """
    _parent = usr(window_index)
    _name = lowerbound(BaseField.txn_variant_name.value)
    _created_by = lowerbound(BaseField.txn_variant_created_by.value)
    return (
        join(_parent, _name),
        join(_parent, _created_by)
    )

def cntl_grid(window_index: int=0, grid_number: int=1) -> str:
    _user_area = usr(window_index)
    _grid = f"cntlGRID{grid_number}"
    return join(
        _user_area, _grid, "shellcont", "shell"
    )

def export_dirpath(window_index: int=1) -> str:
    return ctxt(usr(window_index), "DY_PATH")



class VKey(BaseIntEnum):
    """ 
    Virtual Key [GUI_FKEY Table](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/71d8c95e9c7947ffa197523a232d8143.html) 
    """
    ENTER = 0
    F8 = 8
    SHIFT_F4 = 16
    SHIFT_F5 = 17
    CTRL_F9 = 33
    CTRL_F11 = 35
    CTRL_SHIFT_F7 = 43
    # =========================================================================
    # informative aliases
    # =========================================================================
    GET_TXN_VARIANT = 17
    GET_LIST_STATUS = 35
    EXEC_TXN = 8
    DEFAULT_EXPORT = 16
    MB52_EXPORT = 43


class BaseField(BaseStrEnum):
    """ 
    default field ids... need to handle case where field id is prefixed by another string
    e.g. coois has `S_WERKS` instead of `WERKS` for plant (maybe because it's in a selection container or some subscreen container)
    """
    plant = "WERKS"
    alv_layout = "ALV_DEF"
    movement_type = "BWART"
    posting_date = "BUDAT"
    basic_finish_date = "ECKEN"
    txn_variant_name = "V"
    txn_variant_created_by = "ENAME"
