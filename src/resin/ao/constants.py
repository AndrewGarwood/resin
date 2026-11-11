"""Analysis for Office macro names and public legacy constants."""

from enum import auto
from typing import TypeAlias
from pyqi import BaseStrEnum, BaseIntEnum

COM_ADD_IN_NAME = "SapExcelAddIn"
DEFAULT_AO_DATASOURCE = "DS_1"
EXCEL_ERROR_BASE = -2146826288
XL_ERR_NA = -2146826246


__all__ = [
    "COM_ADD_IN_NAME", "DEFAULT_AO_DATASOURCE", "EXCEL_ERROR_BASE", "XL_ERR_NA",
]
