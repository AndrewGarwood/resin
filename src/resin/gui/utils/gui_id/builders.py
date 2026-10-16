"""
*`@file`* `gui/utils/gui_id/builders`
"""

from __future__ import annotations
from typing import Literal, Optional
from pyqi import (export, require)
from re import match as re_match
from lute import LogMsg
from .enums import (BaseField)
from .factory import *


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


