"""
*`@file`* gui/services/pool/assignment

- for first implementation, using batches: 
"simpler and safer than immediately building a dynamic scheduler where workers 
independently pick up another transaction as soon as they finish."

"""
from .worker import (SessionWorker)
from ..transaction import (Transaction)
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TransactionAssignment:
    transaction: Transaction
    worker: SessionWorker

def assign_batch(
    transactions: list[Transaction],
    workers: list[SessionWorker],
    /,
) -> list[TransactionAssignment]:
    if len(transactions) > len(workers):
        raise ValueError(
            "A batch cannot contain more transactions than workers"
        )

    return [
        TransactionAssignment(transaction, worker)
        for transaction, worker in zip(transactions, workers)
    ]