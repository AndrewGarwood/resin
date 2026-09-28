"""
*`@file`* `gui/models/transaction/layout`

- when able to set layout in transaction parameters, can explicitly declare layout 
here if don't want to put it in Transaction.fields
- (if gets overriden by a default layout, must use _export._layout.LayoutSelector)
"""
from datetime import date
from pathlib import Path
from dataclasses import dataclass, replace
from typing import (Self, TypedDict, Required, NotRequired, Any, Optional, Mapping, TypeAlias, Literal)
from pyqi import (String, Json, export, Result, dt, fs, require)
from lute import LogMsg
from ...utils import gui_id as GUI

class LayoutOptionsDict(TypedDict):
    field_id: str
    name: str


class LayoutOptions(Json.Serial[LayoutOptionsDict]):
    field_id: str
    name: str
    @classmethod
    def from_dict(cls, data: LayoutOptionsDict | dict[str, Any], /) -> Self:
        try:
            name = data.get('name') or data.get('variant')
            return cls(
                field_id=data['field_id'],
                name=require.non_empty_string(name),
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(e, received=Json.serialize(data))) from e
    
    @property
    def variant(self): # temp for backwards compatibility
        return self.name


__all__ = export(LayoutOptions, LayoutOptionsDict)