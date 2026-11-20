"""
*`@file`* `gui/models/transaction/options`
"""
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import (Mapping, Self, TypedDict, Required, Any)
from pyqi import (Json, export, Array, fs, dt)
from lute import LogMsg

from .enums import (ExecutionType)
from .layout import (LayoutOptions, LayoutOptionsDict)
from .variant import (VariantOptions, VariantOptionsDict)
from .multiscreen import (ScreenFieldSelectionDict, ScreenFieldSelection)
from .._export import (ExportOptions, ExportOptionsDict, FileOptions)


class TransactionOptionsDict(TypedDict, total=False):
    code: Required[str]
    id: str
    variant: VariantOptionsDict
    layout: LayoutOptionsDict
    export: ExportOptionsDict
    method: ExecutionType | str
    fields: dict[str, Any]
    screens: list[ScreenFieldSelectionDict]



@dataclass
class TransactionOptions(Json.Serial[TransactionOptionsDict]):
    """
    *`@extends`* `Json.Serial[TransactionOptionsDict]`
    """
    code: str
    _id: str | None = None
    method: ExecutionType = ExecutionType.STANDARD
    fields: dict[str, Any] = field(default_factory=dict)
    """ 
    - `fields` store definitions, resolved at runtime immediately before loading into SAPGUI.
    - these are fields that can be populated on the first screen when starting a transaction
    """
    layout: LayoutOptions | None = None
    variant: VariantOptions | None = None
    export: ExportOptions | None = None
    screens: list[ScreenFieldSelection] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: TransactionOptionsDict | dict[str, Any], /) -> Self:
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
                method=(
                    ExecutionType.resolve(_method_value) if _method_value 
                    else ExecutionType.STANDARD
                ),
                fields=fields,
                layout=LayoutOptions.from_dict(_layout) if _layout else None,
                variant=VariantOptions.from_dict(_variant) if _variant else None,
                export=ExportOptions.from_dict(_export) if _export else None,
                _id=data.get('id', None),
                screens=Array.map(data.get('screens', []), ScreenFieldSelection.from_dict)
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                f"Failed to construct TransactionOptions",
                received=Json.serialize(data)
            )) from e

    def with_fields(
        self, 
        fields: Mapping[str, Any], 
        /, 
        copy_existing: bool=False
    ) -> Self:
        """
        - *`@param`* `fields (Mapping[str, Any])` - entries that will be in returned `TransactionOptions.fields`
        - *`@param`* `copy_existing (bool)` - whether returned 
        `TransactionOptions.fields` will only contain entries in `fields` param or if it will be an updated copy of `self.fields` 
        """
        _result_fields: dict[str, Any] = {} if not copy_existing else { **self.fields }
        _result_fields.update(fields)
        return replace(self, fields=_result_fields, screens=list(self.screens))

    def set_export_path(
        self, 
        path: fs.StrPath | None = None, 
        /, 
        *, 
        ref_date: dt.DateValue | None,
        dt_fmt: str | None = None
    ) -> Path:
        if (not self.export):
            raise ValueError(LogMsg(f"self.export (ExportOptions) is undefined"))

        if (not self.export.file):
            if (not path):
                raise ValueError(LogMsg(f"path must be defined when self.export.file is undefined"))
            self.export.file = FileOptions(
                path=FileOptions.get_formatted_path(
                    path=fs.to_path(path), 
                    ref_date=ref_date, 
                    dt_fmt=dt_fmt
                )
            )
        else:
            self.export.file.path = FileOptions.get_formatted_path(
                path=fs.to_path(path or self.export.file.path),
                ref_date=ref_date,
                dt_fmt=dt_fmt
            )
        
        return self.export.file.path

    def to_dict(self) -> TransactionOptionsDict | dict[str, Any]:
        return {
            "code": self.code,
            "id": self._id,
            "method": self.method,
            "layout": None if self.layout is None else self.layout.to_dict(),
            "variant": None if self.variant is None else self.variant.to_dict(),
            "export": None if self.export is None else self.export.to_dict(),
            "screens": Array.map(self.screens, lambda s: s.to_dict())
        }

    def __str__(self):
        return Json.to_str(self.to_dict())

__all__ = export(TransactionOptions, TransactionOptionsDict)