"""
*`@file`* `gui/utils/gui_id/constants`
"""
from __future__ import annotations
from pyqi import (BaseIntEnum, BaseStrEnum, export)


class VKey(BaseIntEnum):
    """ 
    Virtual Key [GUI_FKEY Table](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/71d8c95e9c7947ffa197523a232d8143.html) 
    """
    ENTER = 0
    F8 = 8
    F9 = 9
    SHIFT_F1 = 13
    SHIFT_F4 = 16
    SHIFT_F5 = 17
    CTRL_S = 11
    CTRL_F9 = 33
    CTRL_F11 = 35
    CTRL_SHIFT_F7 = 43
    # =========================================================================
    # informative aliases
    # =========================================================================
    GET_TXN_VARIANT = 17
    GET_LIST_STATUS = 35
    STANDARD_EXEC_START = 8
    ASYNC_EXEC_OPEN_OPTIONS = 9
    ASYNC_EXEC_START = 11
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


__all__ = export(VKey, BaseField)