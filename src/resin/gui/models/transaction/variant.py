"""
*`@file`* `gui/models/transaction/variant`
"""
from datetime import date
from pathlib import Path
from dataclasses import dataclass, replace
from typing import (Self, TypedDict, Required, NotRequired, Any, Optional, Mapping, TypeAlias, Literal)
from pyqi import (String, Json, export, Result, dt, fs)
from lute import LogMsg
from ...utils import gui_id as GUI


class VariantOptionsDict(TypedDict):
    name: str
    """ name/label of transaction variant """
    created_by: str
    """ user id """


@dataclass
class VariantOptions(Json.Serial[VariantOptionsDict]):
    name: str
    """ name/label of transaction variant """
    created_by: str
    """ user id """
    @classmethod
    def from_dict(cls, data: VariantOptionsDict | dict[str, Any]) -> Self:
        return cls(
            name=data['name'],
            created_by=data['created_by']
        )


__all__ = export(VariantOptionsDict, VariantOptions)