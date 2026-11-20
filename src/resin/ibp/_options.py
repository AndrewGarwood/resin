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
    BaseControllerOptions, 
    BaseControllerOptionsDict
)
from .constants import (DEFAULT_SHEETNAME, IBP_COM_ADDIN_NAME)

class ControllerOptionsDict(BaseControllerOptionsDict, total=False):
    addin_name: str
    connection_mode: str | ConnectionMode
    anchor_seed: str
    anchor_sheetname: str
    stable_seconds: float

@dataclass
class ControllerOptions(BaseControllerOptions):
    addin_name: str = IBP_COM_ADDIN_NAME
    connection_mode: ConnectionMode = ConnectionMode.WORKBOOK
    anchor_seed: Path | None = None
    anchor_sheetname: str = DEFAULT_SHEETNAME
    stable_seconds: float = 2.0

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
                ),
                stable_seconds = require.positive_number(
                    float(data.get('stable_seconds', 2.0))
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
        return {
            **super().to_dict(), # have to check if this gets right entries 
            "addin_name": self.addin_name,
            "connection_mode": self.connection_mode,
            "anchor_seed": str(self.anchor_seed) if self.anchor_seed else None,
            "anchor_sheetname": self.anchor_sheetname,
            "stable_seconds": self.stable_seconds
        }

    # def __str__(self) -> str:
    #     return f"<{self.__cls_name__}>" + Json.stringify(self.to_dict())