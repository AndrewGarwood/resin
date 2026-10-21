"""
*`@file`* `gui/models/transaction/result`
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Self
from pyqi import (export, Result, Telemetry)
from pyqi.utils.module import HasDunderName
from .._export.result import (CompletedExport)
from lute import LogMsg

@dataclass
class TransactionDetails():
    txn_id: str
    code: str
    exec_tel: Telemetry
    exported: CompletedExport | None=None
    status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "txn_id": self.txn_id,
            "code": self.code,
            "exec_tel": self.exec_tel.to_dict(),
            "exported": self.exported.to_dict() if self.exported else None,
            "status": self.status
        }

# @dataclass
# class TransactionResult(Result[TransactionDetails]):
#     """ *`@extends`* `Result[TransactionDetails]` """
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)

#     @classmethod
#     def ok(
#         cls, 
#         source: str | HasDunderName, 
#         /, 
#         data: TransactionDetails | None = None, 
#         message: str | LogMsg | None = None
#     ) -> TransactionResult:
#         return super().ok(source, data, message)

#     ...
# TransactionResult = Result[TransactionDetails]

__all__ = export(TransactionDetails)