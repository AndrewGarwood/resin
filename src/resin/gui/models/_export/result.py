"""
*`@file`* `gui/models/_export/result`
"""
from pathlib import Path
from dataclasses import dataclass, field
from json import dumps
from pyqi import (export, Result, Telemetry)

@dataclass
class ExportDetails:
    path: Path | None = None
    row_count: int | None = None


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

    def path_exists(self):
        """
        *`@returns`* `self.path is not None and self.path.is_file()`
        - not sure if it's possible to do type guard Path on prop of self
            - at least in 3.11.3
        """
        return (self.path is not None and self.path.is_file())
    
    def to_dict(self):
        return {
            "path": str(self.path) if self.path else None,
            "row_count": self.row_count,
            "tel": self.tel.to_dict()
        }

    def __str__(self):
        return dumps(self.to_dict(), indent=4)


__all__ = export(ExportDetails, CompletedExport)
