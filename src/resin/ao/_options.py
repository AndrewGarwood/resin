"""
*`@file`* `ao/_options`
"""
from dataclasses import dataclass
from typing import (Any, Self)
from pyqi import (Json, require, export)
from lute import LogMsg
from resin._workbook.base_controller_options import (
    BaseControllerOptions, BaseControllerOptionsDict
)
from .constants import (COM_ADD_IN_NAME, DEFAULT_AO_DATASOURCE)


class ControllerOptionsDict(BaseControllerOptionsDict, total=False):
    """
    `(BaseControllerOptionsDict, total=False)`
    ```
    # ==== BaseControllerOptionsDict ====
    staging: str
    staging_policy: str | StagingPolicy
    stage_roots: list[str]
    cooldown_seconds: float
    poll_seconds: float
    startup_timeout_seconds: float
    # ====================================
    # AO specific options
    addin_name: str
    default_ds_alias: str
    ```
    """
    addin_name: str
    ds_alias: str


@dataclass
class ControllerOptions(BaseControllerOptions):
    addin_name: str = COM_ADD_IN_NAME
    ds_alias: str = DEFAULT_AO_DATASOURCE
    """ Default Datasource alias to use if `WorkbookOptions.ds_alias` is undefined """

    @classmethod
    def from_dict(
        cls, 
        data: (ControllerOptionsDict  
            | BaseControllerOptionsDict # redundant but get type error without
            | dict[str, Any]
        ), 
        /,
    ) -> Self:
        try:
            return cls(
                **cls.read_base_entries(data),
                addin_name=require.non_empty_string(
                    data.get('addin_name', COM_ADD_IN_NAME)
                ),
                ds_alias=require.non_empty_string(
                    data.get('ds_alias', DEFAULT_AO_DATASOURCE)
                )
            )
        except (KeyError, ValueError): raise
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e,
                f"Failed to create ao.ControllerOptions from dictionary",
                received=Json.serialize(data)
            )) from e
    
    def to_dict(self) -> ControllerOptionsDict | dict[str, Any]:
        return {
            **super().to_dict(), # have to check if this gets right entries
            "addin_name": self.addin_name,
            "ds_alias": self.ds_alias
        }

__all__ = export(
    ControllerOptionsDict, 
    ControllerOptions
)