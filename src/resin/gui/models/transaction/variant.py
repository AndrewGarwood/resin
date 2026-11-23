"""
*`@file`* `gui/models/transaction/variant`
"""
from dataclasses import dataclass
from typing import (Self, TypedDict, Any)
from pyqi import (Json, export)
from lute import LogMsg


class VariantOptionsDict(TypedDict):
    name: str
    """ name/label of transaction variant """
    created_by: str
    """ user id """


@dataclass(repr=False)
class VariantOptions(Json.Serial[VariantOptionsDict]):
    """ 
    *`@extends`* `Json.Serial[VariantOptionsDict]`
    """
    name: str
    """ name/label of transaction variant """
    created_by: str
    """ user id """
    @classmethod
    def from_dict(cls, data: VariantOptionsDict | dict[str, Any], /) -> Self:
        return cls(
            name=data['name'],
            created_by=data['created_by']
        )

    def to_dict(self) -> VariantOptionsDict | dict[str, Any]:
        return {
            "name": self.name,
            "created_by": self.created_by
        }


__all__ = export(VariantOptionsDict, VariantOptions)