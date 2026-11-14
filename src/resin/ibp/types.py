"""
*`@file`* `ibp/types`
"""
from __future__ import annotations
from typing import (Any)
from pyqi import BaseStrEnum, export

class RefreshMethod(BaseStrEnum):
    """
    **deprecated** b/c just gonna use a prop in ControllerOptions like 
    is_api_enabled or api_configuration
    ```
    API = "api"
    PYWINAUTO = "pywinauto"
    ```
    """
    API = "api"
    PYWINAUTO = "pywinauto"

class ConnectionMode(BaseStrEnum):
    """
    ```
    WORKBOOK = "workbook"
    ANCHOR = "anchor"
    ```
    """
    WORKBOOK = "workbook"
    ANCHOR = "anchor"


class WorkbookProperty(BaseStrEnum):
    """
    ```
    CONNECTION_NAME = "SOP_Connection_Name"
    FAVORITE_NAME = "SOP_Favorite_Name"
    REFRESH_TIMESTAMP = "SOP_Refresh_Timestamp"
    TEMPLATE_NAME = "SOP_Template_Name"
    CURRENCY_TO_ID = "SOP_CurrencyToID"
    UNIT_OF_MEASURE_TO_ID = "SOP_UnitofMeasureToID"
    FILTER = "SOP_Filter"
    WB_FILTER = "SOP_WB_Filter"
    PLANNING_SCOPE = "SOP_Planning_Scope"
    ```
    """
    CONNECTION_NAME = "SOP_Connection_Name"
    FAVORITE_NAME = "SOP_Favorite_Name"
    REFRESH_TIMESTAMP = "SOP_Refresh_Timestamp"
    TEMPLATE_NAME = "SOP_Template_Name"
    CURRENCY_TO_ID = "SOP_CurrencyToID"
    UNIT_OF_MEASURE_TO_ID = "SOP_UnitofMeasureToID"
    FILTER = "SOP_Filter"
    WB_FILTER = "SOP_WB_Filter"
    PLANNING_SCOPE = "SOP_Planning_Scope"

    @staticmethod
    def default_formatter(value: Any, /) -> Any:
        if isinstance(value, str) and value.startswith('="') and value.endswith('"'):
            return value[2:-1].replace('""', '"')
        return value


__all__ = export(RefreshMethod, ConnectionMode, WorkbookProperty)
