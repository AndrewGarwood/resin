"""
*`@file`* `gui/models/_export/result`
"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import (Optional)
from pyqi import (export, Result, Telemetry)


@dataclass
class ExportDetails:
    path: Optional[Path]=None
    row_count: Optional[int]=None

@dataclass
class ExportResult(Result[ExportDetails]):
    """ 
    *`@extends`* `Result[TransactionExport]`
    """
    ...

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

__all__ = export(ExportDetails, ExportResult)
