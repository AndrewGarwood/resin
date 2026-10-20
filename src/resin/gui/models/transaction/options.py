"""
*`@file`* `gui/models/transaction/options`
"""
from dataclasses import dataclass, field, replace
from typing import (Mapping, Self, TypedDict, Required, Any)
from pyqi import (Json, export)
from lute import LogMsg

from .enums import (ExecutionType)
from .layout import (LayoutOptions, LayoutOptionsDict)
from .variant import (VariantOptions, VariantOptionsDict)
from .._export import (ExportOptions, ExportOptionsDict)


class TransactionOptionsDict(TypedDict, total=False):
    code: Required[str]
    variant: VariantOptionsDict
    layout: LayoutOptionsDict
    export: ExportOptionsDict
    method: ExecutionType | str
    fields: dict[str, Any]
    id: str


@dataclass
class TransactionOptions(Json.Serial[TransactionOptionsDict]):
    """
    """
    code: str
    _id: str | None = None
    method: ExecutionType = ExecutionType.STANDARD
    fields: dict[str, Any] = field(default_factory=dict)
    layout: LayoutOptions | None = None
    variant: VariantOptions | None = None
    export: ExportOptions | None = None

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
                method=ExecutionType.resolve(_method_value) if _method_value else ExecutionType.STANDARD,
                fields=fields,
                layout=LayoutOptions.from_dict(_layout) if _layout else None,
                variant=VariantOptions.from_dict(_variant) if _variant else None,
                export=ExportOptions.from_dict(_export) if _export else None,
                _id=data.get('id', None)
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(e, received=Json.serialize(data))) from e

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
        return replace(self, fields=_result_fields)

__all__ = export(TransactionOptions, TransactionOptionsDict)