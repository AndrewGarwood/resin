"""
*`@file`* `ibp/_options`
"""
from dataclasses import dataclass
from pathlib import Path
from typing import (TypedDict, Any, Self, Required)
from pyqi import (Json, require, export, fs, Array)
from lute import LogMsg
from .types import (ConnectionMode)

from resin._workbook import (
    StagingPolicy, 
    BaseControllerOptions, 
    BaseControllerOptionsDict
)
from .constants import (DEFAULT_SHEETNAME, IBP_COM_ADDIN_NAME)

class ControllerOptionsDict(TypedDict, total=False):
    staging: Required[str]
    staging_policy: str | StagingPolicy
    stage_roots: list[str]
    cooldown_seconds: float
    poll_seconds: float
    startup_timeout_seconds: float

    addin_name: str
    connection_mode: str | ConnectionMode
    anchor_seed: str
    anchor_sheetname: str

@dataclass
class ControllerOptions(BaseControllerOptions):
    addin_name: str = IBP_COM_ADDIN_NAME
    connection_mode: ConnectionMode = ConnectionMode.WORKBOOK
    anchor_seed: Path | None = None
    anchor_sheetname: str = DEFAULT_SHEETNAME

    @classmethod
    def from_dict(
        cls, 
        data: (ControllerOptionsDict  
            | BaseControllerOptionsDict
            | dict[str, Any]
        ),  
        /
    ) -> Self:
        try:
            _anchor = data.get('anchor_seed') or data.get('anchor')
            if (_anchor is not None):
                _anchor = fs.to_path(require.non_empty_string(
                    _anchor, 
                    "ibp.ControllerOptionsDict['anchor_seed']"
                ))
            return cls(
                **cls.read_base_entries(data),
                addin_name=require.non_empty_string(
                    data.get('addin_name', IBP_COM_ADDIN_NAME)
                ),
                connection_mode=ConnectionMode.resolve(
                    data.get('connection_mode', ConnectionMode.WORKBOOK)
                ),
                anchor_seed=_anchor,
                anchor_sheetname=require.non_empty_string(
                    data.get('anchor_sheetname', DEFAULT_SHEETNAME),
                    "ibp.ControllerOptionsDict['anchor_sheetname']"
                )
            )
        except (KeyError, ValueError): raise
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e,
                f"Failed to create ibp.ControllerOptions from dictionary",
                received=Json.serialize(data)
            )) from e


    def to_dict(self) -> ControllerOptionsDict | dict[str, Any]:
        # {
        #     **super().to_dict(), # have to check if this gets right entries 
        #     ... 
        # }, 
        return ControllerOptionsDict(
            staging=str(self.staging),
            stage_roots=Array.map(self.stage_roots, str),
            staging_policy=(self.staging_policy.value),
            cooldown_seconds=self.cooldown_seconds,
            poll_seconds=self.poll_seconds,
            startup_timeout_seconds=self.startup_timeout_seconds,
            addin_name=self.addin_name,
            connection_mode=self.connection_mode,
            anchor_seed=str(self.anchor_seed) if (self.anchor_seed) else "",
            anchor_sheetname=self.anchor_sheetname
        )