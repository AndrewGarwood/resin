"""
*`@file`* `gui/utils/gui_id/builders`
"""
from __future__ import annotations
from typing import (Literal)
from pyqi import (export, require)
from .enums import (BaseField, ComboTextFieldTabIndex, ComboTextFieldTabId)
from .factory import *
from .constants import *
from .parts import join


def txn_variant_name(window_index: int=1,/) -> str:
    return txt(
        usr(window_index), 
        lowerbound(BaseField.txn_variant_name.value)
    )

def txn_variant_created_by(window_index: int=1,/) -> str:
    return txt(
        usr(window_index), 
        lowerbound(BaseField.txn_variant_created_by.value)
    )

def txn_variant_fields(window_index: int=1,/) -> tuple[str, str]:
    """
    *`@returns`* `(variant_name_field_id, variant_created_by_field_id)`
    """
    _parent = usr(window_index)
    _name = lowerbound(BaseField.txn_variant_name.value)
    _created_by = lowerbound(BaseField.txn_variant_created_by.value)
    return (
        txt(_parent, _name),
        txt(_parent, _created_by)
    )

def cntl_grid(window_index: int=0, grid_number: int=1, /) -> str:
    _user_area = usr(window_index)
    _grid = f"cntlGRID{grid_number}"
    return join(
        _user_area, _grid, "shellcont", "shell"
    )

def export_dialog_dirpath(window_index: int=1, /) -> str:
    return ctxt(usr(window_index), "DY_PATH")

def export_dialog_filename(window_index: int=1, /) -> str:
    return ctxt(usr(window_index), "DY_FILENAME")

def export_dialog_confirm_btn(
    window_index: int=1, 
    toolbar_index: int=0, 
    button_index: int=0, 
/) -> str:
    return tbar_btn(window_index, toolbar_index, button_index)

def execute_txn_btn(
    window_index: int=0, 
    toolbar_index: int=1, 
    button_index: int=8, 
    /
) -> str:
    return tbar_btn(window_index, toolbar_index, button_index)

def cell_index_suffix(*, row: int, col: int=1) -> str:
    """
    *`@returns`* `"[{col},{row}]"` 
    """
    return "".join([
        "[",
        ",".join(str(x) for x in (
            require.positive_integer(col, 'ctxt_cell_column_index'),
            require.non_negative_integer(row, 'ctxt_cell_row_index')
        )),
        "]"
    ])

def ctxt_cell_id(
    field_id: str, 
    /, 
    *, 
    row: int, 
    col: int=1
) -> str:
    """
    *`@returns`* `f"{field_id}[{col},{row}]"`
    """
    return f"{field_id}{cell_index_suffix(row=row, col=col)}"

def ctxt_single_value_field_id(
    window: str | int | None,
    tab_id: Literal[
        ComboTextFieldTabId.INCLUDE_SINGLE_VALUE,
        ComboTextFieldTabId.EXCLUDE_SINGLE_VALUE
    ],
    tab_index: Literal[
        ComboTextFieldTabIndex.INCLUDE_SINGLE_VALUE,
        ComboTextFieldTabIndex.EXCLUDE_SINGLE_VALUE
    ],
    is_exclude: bool=False
) -> str:
    """
    ```
    endpoint: Literal["LOW"] = "LOW", # → SLOW_('E'|'I')
    ```
    """
    return join(
        usr(window),
        TAB_STRIP,
        tabp(tab_id),
        ssub('SCREEN_HEADER', 'SAPLALDB', tab_index),
        tblSAPLALDB('SINGLE', is_exclude=is_exclude),
        f"ctxt{CTXT_MULTI_SELECTION_BASE}-SLOW_{'E' if is_exclude else 'I'}"
    )


def ctxt_interval_field_id(
    window_index: int | None,
    tab_id: Literal[
        ComboTextFieldTabId.INCLUDE_INTERVAL, 
        ComboTextFieldTabId.EXCLUDE_INTERVAL
    ],
    tab_index: Literal[
        ComboTextFieldTabIndex.INCLUDE_INTERVAL, 
        ComboTextFieldTabIndex.EXCLUDE_INTERVAL
    ],
    endpoint: Literal["LOW", "HIGH"],
    is_exclude: bool=False,
) -> str:
    return join(
        usr(window_index),
        TAB_STRIP,
        tabp(tab_id),
        ssub('SCREEN_HEADER', 'SAPLALDB', tab_index),
        tblSAPLALDB('INTERVAL', is_exclude=is_exclude),
        f"ctxt{CTXT_MULTI_SELECTION_BASE}-I{endpoint}_{'E' if is_exclude else 'I'}"
    )

__all__ = export(
    export_dialog_confirm_btn, 
    export_dialog_dirpath, 
    export_dialog_filename,
    cntl_grid,
    txn_variant_created_by,
    txn_variant_name,
    txn_variant_name,
    execute_txn_btn,
    ctxt_cell_id,
    cell_index_suffix,
    ctxt_single_value_field_id, 
    ctxt_interval_field_id
)