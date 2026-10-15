"""
*`@file`* `gui/services/_export/registry`
"""
from __future__ import annotations
from typing import Callable
from pyqi import (TypedRegistry, Result)
from resin.gui.core.session import (Session)
from resin.gui.models._export import (ExportDetails, ExportMethod, ExportOptions)
from .types import NativeSaveDialogOptions


EXPORT_METHOD_REGISTRY: TypedRegistry[
    ExportMethod, 
    [
        Session, 
        ExportOptions, 
        NativeSaveDialogOptions 
            | Callable[..., NativeSaveDialogOptions] 
            | None
    ], 
    Result[ExportDetails]
] = TypedRegistry(
    ExportMethod, 
    normalize_key=ExportMethod.resolve, 
    name="ExportMethodRegistry"
)


__all__ = ["EXPORT_METHOD_REGISTRY"]