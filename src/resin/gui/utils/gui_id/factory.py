"""
*`@file`* `gui/utils/gui_id/factory`
- TODO: standardize param names and types and how they are interpreted...
"""
from __future__ import annotations
from typing import Literal, Optional
from pyqi import (export)
from .parts import (join)



def wnd(index: int = 0, /) -> str:
    """ `Window i` → `'wnd[i]'` """
    return f"wnd[{index}]"

def btn(stem: int | str=0, /) -> str:
    """
    *`@returns`* `f"btn[{stem}]" if (isinstance(stem, int)) else f"btn{stem}" if stem else "btn"`
    """
    return (
        f"btn[{stem}]" if (isinstance(stem, int)) 
        else f"btn{stem}" if stem 
        else "btn"
    )

def tbar(window_index: int | None = 0, toolbar_index: int = 0, /) -> str:
    """ Toolbar; `'wnd[window_index]/tbar[toolbar_index]'` """
    return (
        f"{wnd(window_index)}/tbar[{toolbar_index}]" 
        if window_index is not None 
        else f"tbar[{toolbar_index}]"
    )

def sbar(window_index: int | None=0, /) -> str:
    """ `'wnd[0]/sbar'`, `'sbar'` """
    return f"{wnd(window_index)}/sbar" if window_index is not None else "sbar"

def usr(window: int | str | None=None, /) -> str:
    """
    *`@returns`* 
    - `f"{wnd(window)}/usr" if isinstance(window, int)`
    - `else f"{window}/usr" if (window)` # `is str`
    - `else "usr"`    
    """
    return (
        f"{wnd(window)}/usr" if isinstance(window, int) 
        else f"{window}/usr" if (window) 
        else "usr"
    )

def chk(container_id: str, field_id: str, /) -> str:
    return f"{container_id}/chk{field_id}"

def shell(container_id: str, /) -> str:
    """ *`@returns`* `f"{container_id}/shell"` """
    return f"{container_id}/shell"


def tbar_btn(window_index: int | None, toolbar_index: int, button_index: int, /) -> str:
    """ button """
    return join(
        tbar(window_index, toolbar_index),
        btn(button_index)
    )


def ctxt(parent_id: str | None, field_id: str, /) -> str:
    """ 
    - `GuiCTextField`
    - *`@returns`* `f"{container_id}/ctxt{field_id}" if (container_id) else f"ctxt/{field_id}"`
    ```
    # field id for export directory and filename:
    ctxt(usr(1), "DY_PATH")   # "wnd[1]/usr/ctxtDY_PATH"
    ctxt(usr(1), "DY_FILENAME")   # "wnd[1]/usr/ctxtDY_FILENAME"
    ```
    """
    return f"{parent_id}/ctxt{field_id}" if (parent_id) else f"ctxt/{field_id}"

def txt(container_id: str | None, field_id: str, /) -> str:
    """
    *`@returns`* `f"{container_id}/txt{field_id}" if container_id else f"txt{field_id}"`
    """
    return f"{container_id}/txt{field_id}" if container_id else f"txt{field_id}"

def lbl(container_id: str, row: Optional[int]=None, col: Optional[int]=None) -> str:
    result = join(container_id, "lbl")
    if (isinstance(row, int) and isinstance(col, int)):
        result += f"[{row},{col}]"
    return result

def tabp(item: str | None = None, /) -> str:
    """
    - id of `GuiTab`, child of `GuiTabStrip`
    - *`@returns`* `f"tabp{item or ''}"`
    - i.e. tab_item
    """
    return f"tabp{item or ''}"

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


def tblSAPLALDB(
    _type: Literal["INTERVAL", "SINGLE"], 
    is_exclude: bool=False
) -> str:
    """
    *`@returns`* `f"tblSAPLALDB{tbl_type}{'_E' if is_exclude else ''}"`
    """
    return f"tblSAPLALDB{_type}{'_E' if is_exclude else ''}"

def ssub(
    base: Literal['SCREEN_HEADER'] | str,
    item: Literal['SAPLALDB'] | str | None,
    index: str | int | None = None
) -> str:
    """
    *`@returns`* `"ssub{base}:{item}:{index}"` or just `"ssub{base}"`
    """
    parts = [f"ssub{base}"]
    if (item is not None and index is not None):
        parts.extend((item, str(index)))
    return ":".join(parts)

__all__ = export(
    wnd, btn, tbar, sbar, usr, chk, shell, 
    tbar_btn, ctxt, txt, lbl, okcd, lowerbound, upperbound, 
    tblSAPLALDB, tabp, ssub
)