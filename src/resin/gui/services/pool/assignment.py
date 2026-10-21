"""
*`@file`* gui/services/pool/assignment

- for first implementation, using batches: 
"simpler and safer than immediately building a dynamic scheduler where workers 
independently pick up another transaction as soon as they finish."

"""
from .worker import (SessionWorker)
from ..transaction import (Transaction)
from typing import Sequence
from dataclasses import dataclass
from lute import LogMsg


@dataclass(frozen=True, slots=True)
class TransactionAssignment:
    transaction: Transaction
    worker: SessionWorker

def assign_batch(
    transactions: Sequence[Transaction],
    workers: Sequence[SessionWorker],
    /,
) -> list[TransactionAssignment]:
    if len(transactions) > len(workers):
        raise ValueError(LogMsg(
            "A batch cannot contain more transactions than workers",
            num_transactions=len(transactions),
            num_workers=len(workers)
        ))

    return [
        TransactionAssignment(transaction, worker)
        for transaction, worker in zip(transactions, workers)
    ]