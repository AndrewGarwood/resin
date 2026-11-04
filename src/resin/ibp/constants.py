"""IBP workbook metadata and explicit refresh backends."""
from __future__ import annotations

from typing import Any
from pyqi import BaseStrEnum

from .._workbook import ConnectionBindingError

IBP_COM_ADDIN_NAME = "IBPXLClient.Connect"
IBP_RIBBON_TITLE = "SAP IBP"
DEFAULT_SHEETNAME = "Demand View"
IbpConnectionError = ConnectionBindingError


class RefreshMethod(BaseStrEnum):
    API = "api"
    PYWINAUTO = "pywinauto"


class ConnectionMode(BaseStrEnum):
    WORKBOOK = "workbook"
    ANCHOR = "anchor"


class WorkbookProperty(BaseStrEnum):
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
