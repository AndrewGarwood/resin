"""
*`@file`* `gui/models/transaction/options`
"""
from datetime import date
from enum import auto
from pathlib import Path
from dataclasses import dataclass, field, replace
from typing import (Self, TypedDict, Required, NotRequired, Any, Optional, Mapping, TypeAlias, Literal)
from pyqi import (String, Json, export, Result, dt, fs)
from lute import LogMsg, annotate
from ...utils import gui_id as GUI

from .layout import (LayoutOptions, LayoutOptionsDict)
from .variant import (VariantOptions, VariantOptionsDict)
from .._export import (ExportOptions, ExportOptionsDict)


class ExecuteMethod(String.BaseEnum):
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

    @classmethod
    def from_dict(cls, data: TransactionOptionsDict | dict[str, Any]) -> Self:
        try:
            _method_value = data.get('method', None)
            fields = data.get('fields', dict())
            if (fields and not isinstance(fields, dict)):
                raise TypeError(LogMsg.bad_arg(
                    fields, "fields", "Invalid TransactionOptions.fields", dict
                ))
            _layout = data.get('layout', None)
            _variant = data.get('variant', None)
            _export = data.get('export', None)
            return cls(
                code=data['code'],
                method=ExecuteMethod(_method_value) if _method_value else ExecuteMethod.STANDARD,
                fields=fields,
                layout=LayoutOptions.from_dict(_layout) if _layout else None,
                variant=VariantOptions.from_dict(_variant) if _variant else None,
                export=ExportOptions.from_dict(_export) if _export else None,
                _id=data.get('id', None)
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(e, received=Json.serialize(data)))