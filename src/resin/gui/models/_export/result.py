"""
*`@file`* `gui/models/_export/result`
"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import (Optional, Self)
from pyqi import (export, Result, Telemetry)
from pyqi.utils.module import HasDunderName
from lute import LogMsg

@dataclass
class ExportDetails:
    path: Optional[Path]=None
    row_count: Optional[int]=None


# ExportResult = Result[ExportDetails]
# class ExportResult(Result[ExportDetails]): 
#     """ 
#     *`@extends`* `Result[ExportDetails]`
#     """
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)

@dataclass
class CompletedExport(ExportDetails):
    """ *`@extends`* `ExportDetails`"""
    tel: Telemetry = field(default_factory=Telemetry)
    @classmethod
    def from_details(cls, d: ExportDetails, tel: Telemetry, /):
        return cls(
            path=d.path,
            row_count=d.row_count,
            tel=tel
        )

__all__ = export(ExportDetails, CompletedExport)
