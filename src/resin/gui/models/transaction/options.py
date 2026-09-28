"""
*`@file`* `gui/models/transaction/options`
"""
from datetime import date
from enum import auto
from pathlib import Path
from dataclasses import dataclass, field, replace
from typing import (Self, TypedDict, Required, NotRequired, Any, Optional, Mapping, TypeAlias, Literal)
from pyqi import (String, Json, export, Result, dt, fs)
from lute import LogMsg
from ...utils import gui_id as GUI

from .layout import (LayoutOptions, LayoutOptionsDict)
from .variant import (VariantOptions, VariantOptionsDict)
from .._export import (ExportOptions, ExportOptionsDict)


class ExecuteMethod(String.BaseStrEnum):
    STANDARD = auto()
    BACKGROUND = auto() # Not Yet implemented


class TransactionOptionsDict(TypedDict, total=False):
    code: Required[str]
    variant: VariantOptionsDict
    layout: LayoutOptionsDict
    export: ExportOptionsDict
    method: ExecuteMethod | str
    fields: dict[str, Any]
    id: str


@dataclass
class TransactionOptions(Json.Serial[TransactionOptionsDict]):
    code: str
    _id: str | None = None
    method: ExecuteMethod = ExecuteMethod.STANDARD
    fields: dict[str, Any] = field(default_factory=dict)
    layout: LayoutOptions | None = None
    variant: VariantOptions | None = None
    export: ExportOptions | None = None