"""
*`@file`* `gui/services/_export/registry`
"""
from pyqi import (Registry)
from resin.gui.models._export import (ExportResult, ExportMethod)


EXPORTERS: Registry[ExportMethod, ExportResult] = Registry(
    ExportMethod, 
    normalize_key=ExportMethod.resolve
)