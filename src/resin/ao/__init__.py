"""Analysis for Office controllers, options and macro constants."""

import sys as _sys

from . import _options as _options_module

# Expose both spellings without case-colliding files on Windows.
_sys.modules[__name__ + ".options"] = _options_module
_sys.modules[__name__ + ".Options"] = _options_module

from .constants import *
from ._options import *
from .controller import *

__all__ = [
    "COM_ADD_IN_NAME", "DEFAULT_AO_DATASOURCE", "EXCEL_ERROR_BASE", "XL_ERR_NA",
    "AoResponseTup", "AoProp", "AoResponseCode", "DsAliasState",
    "RefreshActiveStatus", "AoMacro", "AoObjectType", "AoMemberDisplay",
    "AoMeasureDisplay", "AoVariableDisplay", "WorkbookProperty", "AoCmd",
    "WorkbookOptionsDict", "WorkbookOptions", "DefaultValueOptionsDict",
    "DefaultValueOptions", "ControllerOptionsDict", "ControllerOptions",
    "Controller", "AoRefreshDetails", "AoCommandError", "ExcelComValueError",
    "is_excel_error_value", "require_ao_bool", "ensure_sap_ao_ready",
]