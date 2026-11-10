"""Analysis for Office macro names and public legacy constants."""

from enum import auto
from typing import TypeAlias
from pyqi import BaseStrEnum, BaseIntEnum

COM_ADD_IN_NAME = "SapExcelAddIn"
DEFAULT_AO_DATASOURCE = "DS_1"
EXCEL_ERROR_BASE = -2146826288
XL_ERR_NA = -2146826246
AoResponseTup: TypeAlias = tuple[str | None, str | None]

class AoProp(BaseStrEnum):
    CHANGED_DATASOURCES = "ChangedDatasources"
    CHANGED_CROSSTABS = "ChangedCrosstabs"
    NUMBER_OF_NEW_LINES = "NumberOfNewLines"
    LAST_ERROR = "LastError"
    IS_AUTO_REFRESH = "IsAutoRefresh"
    IS_DATA_SOURCE_ACTIVE = "IsDataSourceActive"
    IS_DATA_SOURCE_EDITABLE = "IsDataSourceEditable"
    IS_CONNECTED = "IsConnected"
    HAS_CHANGED_PLAN_DATA = "HasChangedPlanData"

class AoResponseCode(BaseIntEnum):
    SUCCESS = 1
    FAILURE = 0
    DATASOURCE_INVALID = 31
    DATASOURCE_UNRESOLVED = 32

class DsAliasState(BaseStrEnum):
    EXCEL_ERROR = auto()
    INACTIVE_OR_UNRESOLVED = auto()
    ACTIVE = auto()
    USABLE_FOR_VARIABLES = auto()


class RefreshActiveStatus(BaseStrEnum):
    ACTIVE = auto()
    INACTIVE = auto()


class AoMacro(BaseStrEnum):
    EXEC_CMD = "SAPExecuteCommand"
    SET_REFRESH = "SAPSetRefreshBehaviour"
    SET_FILTER = "SAPSetFilter"
    SET_VAR = "SAPSetVariable"
    GET_PROPERTY = "SAPGetProperty"
    GET_SRC_INFO = "SAPGetSourceInfo"
    OPEN_WORKBOOK = "SAPOpenWorkbook"
    MOVE_DIMENSION = "SAPMoveDimension"
    CALL_MEMBER_SELECTOR = "SAPCallMemberSelector"
    LIST_OF = "SAPListOf"
    GET_WORKBOOK_INFO = "SAPGetWorkbookInfo"
    LIST_EFFECTIVE_FILTERS = "SAPListOfEffectiveFilters"
    LIST_MEASURE_FILTERS = "SAPListOfMeasureFilters"
    LIST_VARIABLES = "SAPListOfVariables"
    LIST_DIMENSIONS = "SAPListOfDimensions"
    LIST_MESSAGES = "SAPListOfMessages"
    LIST_STATIC_FILTERS = "SAPListOfStaticFilters"


class AoObjectType(BaseStrEnum):
    DATASOURCES = "DATASOURCES"
    CROSSTABS = "CROSSTABS"
    PLANNINGFUNCTIONS = "PLANNINGFUNCTIONS"
    PLANNINGSEQUENCES = "PLANNINGSEQUENCES"
    CUSTOMAPPLCONTEXT = "CUSTOMAPPLCONTEXT"


class AoMemberDisplay(BaseStrEnum):
    TEXT = "TEXT"
    KEY = "KEY"
    INPUT_STRING = "INPUT_STRING"


class AoMeasureDisplay(BaseStrEnum):
    ALL = "ALL"
    DIMENSION = "DIMENSION "
    MEASURE = "MEASURE"
    BEX = "BEX"


class AoVariableDisplay(BaseStrEnum):
    ALL = "ALL"
    ALL_FILLED = "ALL_FILLED"
    PROMPTS = "PROMPTS"
    PROMPTS_FILLED = "PROMPTS_FILLED"
    PLAN_PARAMETER = "PLAN_PARAMETER"


class WorkbookProperty(BaseStrEnum):
    NAME = "WorkbookName"
    DESCRIPTION = "WorkbookDescription"
    CREATED_BY = "CreatedBy"
    CREATED_AT = "CreatedAt"
    LAST_CHANGED_AT = "LastChangedAt"
    LAST_REFRESHED_AT = "LastRefreshedAt"
    LOGON_USER = "LogonUser"
    PLANNING_ENVIRONMENT = "PlanningEnvironment"
    PLANNING_MODEL = "PlanningModel"


class AoCmd(BaseStrEnum):
    PAUSE_VARIABLE_SUBMIT = "PauseVariableSubmit"
    REFRESH = "Refresh"
    REFRESH_DATA = "RefreshData"
    RESTART_DATASOURCE = "Restart"
    SET_AUTOREFRESH = "AutoRefresh"
    HIDE = "Hide"
    SHOW = "Show"


__all__ = [
    "COM_ADD_IN_NAME", "DEFAULT_AO_DATASOURCE", "EXCEL_ERROR_BASE", "XL_ERR_NA",
    "AoResponseTup", "AoProp", "AoResponseCode", "DsAliasState",
    "RefreshActiveStatus", "AoMacro", "AoObjectType", "AoMemberDisplay",
    "AoMeasureDisplay", "AoVariableDisplay", "WorkbookProperty", "AoCmd",
]
