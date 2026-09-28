"""
*`@file`* `gui/models/_export/layout`
"""
from dataclasses import dataclass
from typing import (TypedDict, Required, NotRequired, Any, Optional, Mapping)
from pyqi import (String, Json, require, validate, export)
from lute import (LogMsg)


class LayoutSelectorDict(TypedDict):
    """
    configure layout selection made after the transaction finishes executing
    """
    button_id: NotRequired[str] # clicking button opens layout grid
    vkey: NotRequired[int] # sending vkey opens layout grid
    grid_id: str
    """ 
    (shell with subtype = GridView)
    - e.g. `"wnd[1]/usr/ssubD0500_SUBSCREEN:SAPLSLVC_DIALOG:0501/cntlG51_CONTAINER/shellcont/shell"`
    """
    name: str
    """ i.e. layout variant name """

@dataclass
class LayoutSelector(Json.Serial[LayoutSelectorDict]):
    """
    select layout after transaction executes.
    - (e.g. if the transaction uses an un-wanted default layout)
    """
    name: str
    grid_id: str
    _btn_id: Optional[str]=None
    _vkey: Optional[int]=None
    def __init__(
        self, 
        name: str, 
        grid_id: str, 
        button_id: Optional[str]=None, 
        vkey: Optional[int]=None
    ):
        self.name = require.non_empty_string(name, "LayoutSelector.name")
        self.grid_id = require.non_empty_string(grid_id, "LayoutSelector.grid_id")
        if (not button_id and not vkey):
            raise ValueError(LogMsg(
                "Invalid LayoutSelector:",
                "one of [button_id (str), vkey (int)] is required",
                self_name=self.name
            ))
        self._btn_id = button_id
        self._vkey = vkey

    @property
    def btn_id(self) -> str:
        return require.non_empty_string(
            self._btn_id, 
            f"{self.name} LayoutSelector.btn_id"
        )

    @property
    def vkey(self) -> int:
        return require.positive_integer(
            self._vkey, 
            f"{self.name} LayoutSelector.vkey"
        )

    @classmethod
    def from_dict(cls, data: LayoutSelectorDict | Mapping[str, Any]):
        try:
            grid_id = data.get("grid_id")
            if not grid_id:
                raise ValueError("Invalid LayoutSelectorDict. grid_id is required")
            layout_name = data.get("name")
            if not layout_name:
                raise ValueError("Invalid LayoutSelectorDict. name is required")
            return cls(
                name=layout_name,
                grid_id=grid_id,
                button_id=data.get("button_id"),
                vkey=data.get("vkey")
            )
        except Exception as e:
            raise Exception(LogMsg.err(error=e, received=Json.serialize(data))) from e


__all__ = export(LayoutSelector, LayoutSelectorDict)