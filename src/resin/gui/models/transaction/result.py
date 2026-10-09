"""
*`@file`* `gui/models/transaction/result`
"""
from dataclasses import dataclass
from pyqi import (export, Result, Telemetry)
from .._export.result import (CompletedExport)

@dataclass
class TransactionDetails():
    txn_id: str
    code: str
    exec_tel: Telemetry
    exported: CompletedExport | None=None

# @dataclass
# class TransactionResult(Result[TransactionDetails]):
#     """ *`@extends`* `Result[TransactionDetails]` """
#     ...
TransactionResult = Result[TransactionDetails]

__all__ = export(TransactionDetails, TransactionResult)