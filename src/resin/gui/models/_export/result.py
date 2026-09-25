"""
*`@file`* `gui/models/_export/result`
"""
from pathlib import Path
from dataclasses import dataclass
from typing import (Optional)
from pyqi import (export, Result)


@dataclass
class TransactionExport:
    path: Optional[Path]=None
    row_count: Optional[int]=None

class ExportResult(Result[TransactionExport]):
    """ 
    *`@extends`* `Result[TransactionExport]`
    """
    ...

__all__ = export(TransactionExport, ExportResult)
