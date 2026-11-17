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
    F3 = 3
    F5 = 5
    F8 = 8
    F9 = 9
    SHIFT_F1 = 13
    SHIFT_F3 = 15
    SHIFT_F4 = 16
    SHIFT_F5 = 17
    SHIFT_F12 = 24
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
    TXN_GO_BACK = 3
    TXN_NEXT_SCREEN = 5
    TXN_CANCEL = 12 # F12
    TXN_EXIT = 15 # exit txn back to user menu
    EXIT_SESSION = 15 # 


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

"""
CTXT_INCLUDE_SINGLE_VALUE_TAB_ID = "SIVA"
CTXT_INCLUDE_RANGE_TAB_ID = "INTL"

CTXT_EXCLUDE_SINGLE_VALUE_TAB_ID = "NOSV"
CTXT_EXCLUDE_RANGE_TAB_ID = "NOINT"

CTXT_INCLUDE_SINGLE_VALUE_SUBSCREEN_INDEX = "3010"
CTXT_INCLUDE_RANGE_SUBSCREEN_INDEX = "3020"

CTXT_EXCLUDE_SINGLE_VALUE_SUBSCREEN_INDEX = "3030"
CTXT_EXCLUDE_RANGE_SUBSCREEN_INDEX = "3040"
"""

class ComboTextFieldTabId(BaseStrEnum):
    """
    ```
    INCLUDE_SINGLE_VALUE = "SIVA"
    INCLUDE_INTERVAL = "INTL"
    EXCLUDE_SINGLE_VALUE = "NOSV"
    EXCLUDE_INTERVAL = "NOINT"
    ```
    """
    INCLUDE_SINGLE_VALUE = "SIVA"
    INCLUDE_INTERVAL = "INTL"
    EXCLUDE_SINGLE_VALUE = "NOSV"
    EXCLUDE_INTERVAL = "NOINT"
    
    @classmethod
    def single_value_tab_ids(cls):
        return (cls.INCLUDE_SINGLE_VALUE, cls.EXCLUDE_SINGLE_VALUE)

    @classmethod
    def interval_tab_ids(cls):
        return (cls.INCLUDE_INTERVAL, cls.EXCLUDE_INTERVAL)

class ComboTextFieldTabIndex(BaseStrEnum):
    """
    ```
    INCLUDE_SINGLE_VALUE = "3010"
    INCLUDE_INTERVAL = "3020"
    EXCLUDE_SINGLE_VALUE = "3030"
    EXCLUDE_INTERVAL = "3040"
    ```
    """
    INCLUDE_SINGLE_VALUE = "3010"
    INCLUDE_INTERVAL = "3020"
    EXCLUDE_SINGLE_VALUE = "3030"
    EXCLUDE_INTERVAL = "3040"

class ComboTextFieldSelectionType(BaseStrEnum):
    """
    ```
    INTERVAL = "INTERVAL"
    SINGLE_VALUE = "SINGLE"
    ```
    """
    INTERVAL = "INTERVAL"
    SINGLE_VALUE = "SINGLE"

__all__ = export(
    VKey, 
    BaseField, 
    ComboTextFieldTabId, 
    ComboTextFieldTabIndex, 
    ComboTextFieldSelectionType
)