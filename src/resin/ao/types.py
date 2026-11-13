"""
*`@file`* `ao/types`
"""
from dataclasses import dataclass
from datetime import datetime
from enum import auto
from typing import (TypeAlias, Any)
from json import dumps
from pyqi import (BaseStrEnum, BaseIntEnum, export)
from resin._workbook.exceptions import WorkbookControllerError

AoResponseTup: TypeAlias = tuple[
    str | None, 
    str | None
]
""" `(response_code, message)` """

class AoProp(BaseStrEnum):
    """
    [SAPGetProperty](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f27123b76c9b1014bf2c9a7eb0e91070.html)
    - e.g. `Application.Run("SAPGetProperty", "IsConnected", "DS_1")`
    """
    CHANGED_DATASOURCES = "ChangedDatasources"
    CHANGED_CROSSTABS = "ChangedCrosstabs"
    NUMBER_OF_NEW_LINES = "NumberOfNewLines"
    """ `get the number of new lines for a crosstab.` """
    LAST_ERROR = "LastError"
    IS_AUTO_REFRESH = "IsAutoRefresh"
    IS_DATA_SOURCE_ACTIVE = "IsDataSourceActive"
    IS_DATA_SOURCE_EDITABLE = "IsDataSourceEditable"
    IS_CONNECTED = "IsConnected"
    HAS_CHANGED_PLAN_DATA = "HasChangedPlanData"

class AoResponseCode(BaseIntEnum):
    """
    ```
    SUCCESS = 1
    FAILURE = 0
    DATASOURCE_INVALID = 31
    DATASOURCE_UNRESOLVED = 32
    ```
    """
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
    """
    ```
    ACTIVE = auto()
    INACTIVE = auto()
    ```
    """
    ACTIVE = auto()
    INACTIVE = auto()

class AoMacro(BaseStrEnum):
    """ 
    use in param 'macro' in `_xl_run(excel, macro: str, *args: Any)`
    
    - *`@note`* availability of some api macros/functions is dependent on 
    user org's global configuration policy

    - [Working with macros](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f270fd456c9b1014bf2c9a7eb0e91070.html#:~:text=Troubleshooting-,Working%20with%20macros,-Analysis%20contains%20API)
    - [Working with formulas](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f2724b0e6c9b1014bf2c9a7eb0e91070.html#analysis-functions)
    """
    EXEC_CMD = "SAPExecuteCommand"
    SET_REFRESH = "SAPSetRefreshBehaviour"
    SET_FILTER = "SAPSetFilter"
    """ [SAPSetFilter](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f27134636c9b1014bf2c9a7eb0e91070.html#:~:text=Troubleshooting-,SAPSetFilter,-With%20this%20API) """

    SET_VAR = "SAPSetVariable"
    GET_PROPERTY = "SAPGetProperty"
    GET_SRC_INFO = "SAPGetSourceInfo"
    OPEN_WORKBOOK = "SAPOpenWorkbook"
    MOVE_DIMENSION = "SAPMoveDimension"
    """ [SAPMoveDimension](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f2712f176c9b1014bf2c9a7eb0e91070.html#:~:text=Troubleshooting-,SAPMoveDimension,-With%20this%20API)"""
    CALL_MEMBER_SELECTOR = "SAPCallMemberSelector"
    """ [SAPCallMemberSelector](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f27108806c9b1014bf2c9a7eb0e91070.html?version=2.8.18.0#:~:text=Troubleshooting-,SAPCallMemberSelector,-With%20this%20API)"""
    LIST_OF = "SAPListOf"
    GET_WORKBOOK_INFO = "SAPGetWorkbookInfo"
    LIST_EFFECTIVE_FILTERS = "SAPListOfEffectiveFilters"
    """ [SAPListOfEffectiveFilters](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f27094b46c9b1014bf2c9a7eb0e91070.html) """

    LIST_MEASURE_FILTERS = "SAPListOfMeasureFilters"
    LIST_VARIABLES = "SAPListOfVariables"
    """ [SAPListOfVariables](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f270ab186c9b1014bf2c9a7eb0e91070.html#:~:text=Troubleshooting-,SAPListOfVariables,-This%20function%20returns) """

    LIST_DIMENSIONS = "SAPListOfDimensions"
    """ 
    [SAPListOfDimensions](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f2708a156c9b1014bf2c9a7eb0e91070.html#:~:text=Troubleshooting-,SAPListOfDimensions,-This%20function%20returns)
    """
    LIST_MESSAGES = "SAPListOfMessages"
    """ [SAPListOfMessages](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f2709f8f6c9b1014bf2c9a7eb0e91070.html#:~:text=Troubleshooting-,SAPListOfMessages,-This%20function%20includes)"""

    LIST_STATIC_FILTERS = "SAPListOfStaticFilters"


class AoObjectType(BaseStrEnum):
    """ 
    ```
    DATASOURCES = "DATASOURCES"
    CROSSTABS = "CROSSTABS"
    PLANNINGFUNCTIONS = "PLANNINGFUNCTIONS"
    PLANNINGSEQUENCES = "PLANNINGSEQUENCES"
    CUSTOMAPPLCONTEXT = "CUSTOMAPPLCONTEXT"
    ```
    use in/with:
    - `SAPListOf` 

    """
    DATASOURCES = "DATASOURCES"
    CROSSTABS = "CROSSTABS"
    """ returns a list with three columns (Alias, Description and data source Alias) """
    PLANNINGFUNCTIONS = "PLANNINGFUNCTIONS"
    PLANNINGSEQUENCES = "PLANNINGSEQUENCES"
    CUSTOMAPPLCONTEXT = "CUSTOMAPPLCONTEXT"
    """ returns a list with three columns (SystemID, RowCount and Content) """


class AoMemberDisplay(BaseStrEnum):
    """
    ```
    TEXT = "TEXT"
    KEY = "KEY"
    INPUT_STRING = "INPUT_STRING"
    ``` 
    use in/with:
    - `SAPListOfEffectiveFilters` 
    - `SAPListOfVariables` 
    """
    TEXT = "TEXT"
    KEY = "KEY"
    INPUT_STRING = "INPUT_STRING"


class AoMeasureDisplay(BaseStrEnum):
    """ 
    ```
    ALL = "ALL"
    DIMENSION = "DIMENSION "
    MEASURE = "MEASURE"
    BEX = "BEX"
    ```
    use in/with:
    -  `SAPListOfMeasureFilters` 
    """
    ALL = "ALL"
    DIMENSION = "DIMENSION "
    MEASURE = "MEASURE"
    BEX = "BEX"


class AoVariableDisplay(BaseStrEnum):
    """ 
    ```
    ALL = "ALL"
    ALL_FILLED = "ALL_FILLED"
    PROMPTS = "PROMPTS"
    PROMPTS_FILLED = "PROMPTS_FILLED"
    PLAN_PARAMETER = "PLAN_PARAMETER"
    ```
    use in/with: 
    - [SAPListOfVariables](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f270ab186c9b1014bf2c9a7eb0e91070.html#:~:text=Troubleshooting-,SAPListOfVariables,-This%20function%20returns) 
    """
    ALL = "ALL"
    ALL_FILLED = "ALL_FILLED"
    PROMPTS = "PROMPTS"
    PROMPTS_FILLED = "PROMPTS_FILLED"
    PLAN_PARAMETER = "PLAN_PARAMETER"


class WorkbookProperty(BaseStrEnum):
    """ 
    ```
    NAME = "WorkbookName"
    DESCRIPTION = "WorkbookDescription"
    CREATED_BY = "CreatedBy"
    CREATED_AT = "CreatedAt"
    LAST_CHANGED_AT = "LastChangedAt"
    LAST_REFRESHED_AT = "LastRefreshedAt"
    LOGON_USER = "LogonUser"
    PLANNING_ENVIRONMENT = "PlanningEnvironment"
    PLANNING_MODEL = "PlanningModel"
    ```
    use in/with: 
    - `SAPGetWorkbookInfo`
    """
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
    """ 
    ```
    PAUSE_VARIABLE_SUBMIT = "PauseVariableSubmit"
    REFRESH = "Refresh"
    REFRESH_DATA = "RefreshData"
    RESTART_DATASOURCE = "Restart"
    SET_AUTOREFRESH = "AutoRefresh"
    HIDE = "Hide"
    SHOW = "Show"
    ```
    use in/with:
    - `SapExecuteCommand` i.e. `excel.Application.Run("SapExecuteCommand", <here>, ... )`
    """
    PAUSE_VARIABLE_SUBMIT = "PauseVariableSubmit"
    REFRESH = "Refresh"
    """ [Refresh](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f2710db86c9b1014bf2c9a7eb0e91070.html#refresh)"""
    REFRESH_DATA = "RefreshData"
    """ [RefreshData](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f2710db86c9b1014bf2c9a7eb0e91070.html#refreshdata) """
    RESTART_DATASOURCE = "Restart"
    """ [Restart](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f2710db86c9b1014bf2c9a7eb0e91070.html#restart) """
    SET_AUTOREFRESH = "AutoRefresh"
    """ [AutoRefresh](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f2710db86c9b1014bf2c9a7eb0e91070.html#autorefresh) """
    HIDE = "Hide"
    """ 
    [Hide/Show](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f2710db86c9b1014bf2c9a7eb0e91070.html#hide/show)
    """
    SHOW = "Show"
    """ 
    [Hide/Show](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f2710db86c9b1014bf2c9a7eb0e91070.html#hide/show) 
    """


class AoCommandError(WorkbookControllerError):
    """AO rejected a command, prompt or completion observation."""

@dataclass(frozen=True)
class AoRefreshDetails:
    ds_alias: str
    prompts_applied: tuple[str, ...] = ()
    responses: tuple[tuple[str, int], ...] = ()
    completion_verified: bool = False
    live_semantics_verified: bool = False
    last_data_update: Any | None = None
    last_data_update_max: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ds_alias": self.ds_alias,
            "prompts_applied": list(self.prompts_applied),
            "responses": list[self.responses],
            "completion_verified": self.completion_verified,
            "live_semantics_verified": self.live_semantics_verified,
            "last_data_update": self.get_last_data_update(),
            "last_data_update_max": self.get_last_data_update_max()
        }

    def __str__(self):
        return "<AoRefreshDetails>" + dumps(self.to_dict(), indent=4)

    def get_last_data_update(self):
        val = self.last_data_update
        return (
            val.isoformat() if isinstance(val, datetime) 
            else str(val) if val is not None 
            else None
        )
    def get_last_data_update_max(self):
        val = self.last_data_update_max
        return (
            val.isoformat() if isinstance(val, datetime) 
            else str(val) if val is not None 
            else None
        )


__all__ =  export(
    "AoResponseTup",
    AoCommandError,
    AoProp,
    AoResponseCode,
    AoCmd,
    AoMacro,
    WorkbookProperty,
    AoVariableDisplay,
    AoMemberDisplay,
    AoMeasureDisplay,
    AoObjectType,
    DsAliasState,
    RefreshActiveStatus,
    AoRefreshDetails,
    )