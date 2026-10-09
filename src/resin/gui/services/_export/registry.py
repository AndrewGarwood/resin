"""
*`@file`* `gui/services/_export/registry`
"""
from pyqi import (Registry, Result)
from resin.gui.models._export import (ExportResult, ExportMethod)


EXPORT_METHOD_REGISTRY: Registry[ExportMethod, ExportResult] = Registry(
    ExportMethod, 
    normalize_key=ExportMethod.resolve
)

__all__ = ["EXPORT_METHOD_REGISTRY"]