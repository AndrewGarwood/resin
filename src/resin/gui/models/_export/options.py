"""
*`@file`* `gui/models/_export/options`
"""
from dataclasses import dataclass, field
from typing import (Self, TypedDict, Any)
from pyqi import (Json, export)
from lute import LogMsg

from ._file import (FileOptions, FileOptionsDict)
from .layout import (LayoutSelector, LayoutSelectorDict)
from .dialog import (SaveDialog, SaveDialogDict)
from ._method import (ExportMethod, InvokeMethodOptions, InvokeMethodOptionsDict)


class ExportOptionsDict(TypedDict, total=False):
    method: str
    overwrite: bool
    layout: LayoutSelectorDict
    invoke: InvokeMethodOptionsDict
    file: FileOptionsDict
    save: SaveDialogDict

@dataclass
class ExportOptions(Json.Serial[ExportOptionsDict]):
    method: ExportMethod = ExportMethod.NONE
    layout: LayoutSelector | None = None
    invoke: InvokeMethodOptions = field(default_factory=InvokeMethodOptions)
    file: FileOptions = field(default_factory=FileOptions)
    save: SaveDialog = field(default_factory=SaveDialog)
    overwrite: bool = False

    @classmethod
    def from_dict(cls, data: ExportOptionsDict | dict[str, Any], /) -> Self:
        try:
            _method = data.get("method", ExportMethod.NONE.value)
            _layout = data.get("layout", None)
            _invoke = data.get("invoke", None)
            _file = data.get("file", None)
            _save = data.get("save", None)
            return cls(
                method=ExportMethod(_method),
                overwrite=data.get("overwrite", False),
                layout=LayoutSelector.from_dict(_layout) if _layout else None,
                invoke=(
                    InvokeMethodOptions.from_dict(_invoke) if _invoke 
                    else InvokeMethodOptions()
                ),
                file=FileOptions.from_dict(_file) if _file else FileOptions(),
                save=SaveDialog.from_dict(_save) if _save else SaveDialog()
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                received=Json.serialize(data)
            ))


__all__ = export(ExportOptions, ExportOptionsDict)