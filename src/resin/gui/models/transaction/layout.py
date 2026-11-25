"""
*`@file`* `gui/models/transaction/layout`

- when able to set layout in transaction parameters, can explicitly declare layout 
here if don't want to put it in Transaction.fields
- (if gets overriden by a default layout, must use _export._layout.LayoutSelector)
"""
from dataclasses import dataclass
from typing import (Self, TypedDict, Any, )
from pyqi import (Json, export, require)
from lute import LogMsg

class LayoutOptionsDict(TypedDict):
    field_id: str
    name: str

@dataclass(repr=False)
class LayoutOptions(Json.Serial[LayoutOptionsDict]):
    """
    - `@dataclass(repr=False)`
    - *`@extends`* `Json.Serial[LayoutOptionsDict]`
    - *`@note`* `LayoutOptions.from_dict(data)` gets `self.name` from `data.get('name') or data.get('variant')`
    """
    field_id: str
    name: str
    @classmethod
    def from_dict(cls, data: LayoutOptionsDict | dict[str, Any], /) -> Self:
        try:
            name = data.get('name') or data.get('variant')
            return cls(
                field_id=data['field_id'],
                name=require.non_empty_string(name, "LayoutOptions.name"),
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(e, received=Json.serialize(data))) from e
    
    @property
    def variant(self): # temp for backwards compatibility
        return self.name

    def to_dict(self) -> LayoutOptionsDict | dict[str, Any]:
        return {
            "field_id": self.field_id,
            "name": self.name
        }
    


__all__ = export(LayoutOptions, LayoutOptionsDict)