"""
*`@file`* `ibp/global_configuration`

- [Enabling SAP IBP APIs](https://help.sap.com/docs/SAP_INTEGRATED_BUSINESS_PLANNING/b28ffdd739bf45678ef36c44e64652d7/2277db899c02476ea972b101f1302456.html)

"""
from dataclasses import dataclass
from pyqi import (Json, BaseStrEnum, export)
from typing import (Any, Self, TypedDict, NotRequired)

class PlanningViewPermissionLevel(BaseStrEnum):
    """
    ```
    NONE = "none"
    READ = "read"
    SIMULATE = "simulate"
    SAVE = "save"
    ```
    """
    NONE = "none"
    READ = "read"
    SIMULATE = "simulate"
    SAVE = "save"

AUTHORIZED_TO_REFRESH = frozenset([
    PlanningViewPermissionLevel.READ,
    PlanningViewPermissionLevel.SIMULATE,
    PlanningViewPermissionLevel.SAVE
])

class MasterDataPermissionLevel(BaseStrEnum):
    """
    ```
    NONE = "none"
    READ = "read"
    WRITE = "write"
    ```
    """
    NONE = "none"
    READ = "read"
    WRITE = "write"

class GlobalConfigurationDict(TypedDict, total=False):
    EXCEL_PLANNING_VIEW_APIS: str | PlanningViewPermissionLevel
    EXCEL_MASTER_DATA_APIS: NotRequired[str | MasterDataPermissionLevel]


@dataclass(frozen=True)
class GlobalConfiguration(Json.Serial[GlobalConfigurationDict]):
    """
    *`@extends`* `Json.Serial[GlobalConfigurationDict]`
    - [Enabling SAP IBP APIs](https://help.sap.com/docs/SAP_INTEGRATED_BUSINESS_PLANNING/b28ffdd739bf45678ef36c44e64652d7/2277db899c02476ea972b101f1302456.html)
    """
    EXCEL_PLANNING_VIEW_APIS: PlanningViewPermissionLevel = PlanningViewPermissionLevel.NONE
    EXCEL_MASTER_DATA_APIS: MasterDataPermissionLevel = MasterDataPermissionLevel.NONE

    @classmethod
    def from_dict(cls, data: GlobalConfigurationDict | dict[str, Any], /) -> Self:
        return cls(
            EXCEL_PLANNING_VIEW_APIS=PlanningViewPermissionLevel.resolve(
                data.get('EXCEL_PLANNING_VIEW_APIS', PlanningViewPermissionLevel.NONE)
            ),
            EXCEL_MASTER_DATA_APIS=MasterDataPermissionLevel.resolve(
                data.get('EXCEL_MASTER_DATA_APIS', MasterDataPermissionLevel.NONE)
            )
        )

    @property
    def refresh_enabled(self):
        return (self.EXCEL_MASTER_DATA_APIS in AUTHORIZED_TO_REFRESH)


__all__ = export(
    MasterDataPermissionLevel, 
    PlanningViewPermissionLevel, 
    GlobalConfigurationDict, 
    GlobalConfiguration,
    "AUTHORIZED_TO_REFRESH"
)