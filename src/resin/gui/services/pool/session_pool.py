"""
*`@file`* `gui/services/pool/session_pool`

"the pool constructs workers from bindings, and the worker is the only object 
that resolves, uses, and conditionally closes its bound session."
"""
from __future__ import annotations
from collections.abc import Iterable
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any, Self, Sequence
from resin.gui.services.transaction import Transaction
from resin.gui.models.transaction import (TransactionStage, TransactionResult)
from .options import (SessionPoolOptions)
from .worker import (SessionWorker)
from .assignment import (TransactionAssignment, assign_batch)
from .waiters import (wait_for_commands)
from .types import (PendingCommand)
from .command import (SessionCommandType)
from .session_binding import (SessionBinding)
from .session_locator import (SessionLocator)
from .exceptions import (SessionPoolError)
from pyqi import (Arbitrary, resolve_arbitrary, Array)

from lute import (LogMsg)


class SessionPool():
    options: SessionPoolOptions
    _started: bool
    _closed: bool
    _workers: list[SessionWorker]
    def __init__(
        self, 
        bindings: Arbitrary[SessionBinding],
        options: SessionPoolOptions | None = None
    ):
        binding_list = resolve_arbitrary(bindings)
        self.validate_bindings(binding_list)
        self._workers = [
            SessionWorker(str(i), b) 
            for i, b in enumerate(binding_list)
        ]
        if (not self._workers):
            raise ValueError(
                f"SessionPool requires at least 1 SessionBinding"
            )
        self.options = options or SessionPoolOptions()
        self._started = False
        self._closed = False


    @property
    def size(self) -> int:
        return len(self._workers)

    @property
    def workers(self) -> tuple[SessionWorker, ...]:
        return tuple(self._workers)

    def __enter__(self) -> SessionPool:
        self.start()
        return self
        
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        self.close()

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("SessionPool has been closed")

        if self._started:
            return

        started: list[SessionWorker] = []

        try:
            for worker in self._workers:
                worker.start(
                    timeout=self.options.worker_start_timeout
                )
                started.append(worker)

        except BaseException:
            self._stop_workers(started)
            raise

        self._started = True

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._stop_workers(self._workers)
        finally:
            self._closed = True
            self._started = False

    def _stop_workers(
        self,
        workers: Iterable[SessionWorker],
        /,
    ) -> None:
        """
        uses two passes, collects failures
        """
        worker_list = list(workers)
        stop_requests: list[tuple[SessionWorker, Future[None]]] = []
        errors: list[BaseException] = []
        for worker in worker_list:
            try:
                stop_requests.append(
                    (worker, worker.stop())
                )
            except BaseException as error:
                errors.append(error)

        for worker, future in stop_requests:
            try:
                future.result(
                    timeout=self.options.stop_timeout
                )
            except BaseException as error:
                errors.append(error)

        for worker in worker_list:
            try:
                worker.join(
                    timeout=self.options.stop_timeout
                )
            except BaseException as error:
                errors.append(error)

        if errors:
            raise SessionPoolError(
                "One or more session workers failed during shutdown",
                errors=[
                    ("pool-shutdown", error)
                    for error in errors
                ],
            )

    def run(
        self,
        transactions: Arbitrary[Transaction], 
        /,
    ):
        self._require_started()
        txns = list(resolve_arbitrary(transactions))
        self.validate_transactions(txns)
        results: list[TransactionResult] = []
        for batch_start in range(0, len(txns), self.size):
            batch = txns[batch_start: batch_start + self.size]
            assignments = assign_batch(batch, self._workers)
            self._run_batch(assignments)
            results.extend(Array.map(batch, lambda t: t.get_result()))

        return results

    def _run_batch(
        self,
        assignments: list[TransactionAssignment],
        /,
    ) -> None:
        self._run_parallel_phase(
            assignments,
            SessionCommandType.PREPARE,
            timeout=self.options.prepare_timeout,
        )

        self._require_stages(
            assignments,
            {TransactionStage.READY_TO_EXECUTE},
            phase="prepare",
        )

        self._run_parallel_phase(
            assignments,
            SessionCommandType.EXECUTE,
            timeout=self.options.execute_timeout,
        )

        self._require_stages(
            assignments,
            {TransactionStage.POST_EXECUTE},
            phase="execute",
        )

        self._run_parallel_phase(
            assignments,
            SessionCommandType.POST_EXECUTE,
            timeout=self.options.post_execute_timeout,
        )

        self._require_stages(
            assignments,
            {
                TransactionStage.READY_TO_EXPORT,
                TransactionStage.COMPLETED,
            },
            phase="post-execute",
        )

        self._run_exports_sequentially(assignments)

        self._require_stages(
            assignments,
            {TransactionStage.COMPLETED},
            phase="export",
        )

    def _run_parallel_phase(
        self,
        assignments: Iterable[TransactionAssignment],
        command_type: SessionCommandType,
        /,
        *,
        timeout: float | None,
    ) -> None:
        pending = [
            PendingCommand(
                assignment=assignment,
                future=assignment.worker.submit(
                    command_type,
                    assignment.transaction,
                ),
            )
            for assignment in assignments
        ]

        wait_for_commands(
            pending,
            timeout=timeout,
        )

    def _run_exports_sequentially(
        self,
        assignments: Iterable[TransactionAssignment],
        /,
    ) -> None:
        for assignment in assignments:
            transaction = assignment.transaction

            if transaction.stage is TransactionStage.COMPLETED:
                continue

            if transaction.stage is not TransactionStage.READY_TO_EXPORT:
                raise RuntimeError(
                    f"Transaction {transaction.id!r} cannot export "
                    f"from stage {transaction.stage!s}"
                )

            future = assignment.worker.submit(
                SessionCommandType.EXPORT,
                transaction,
            )

            # Wait immediately before submitting the next export.
            wait_for_commands(
                [
                    PendingCommand(
                        assignment=assignment,
                        future=future,
                    )
                ],
                timeout=self.options.export_timeout,
            )

    def _require_stages(
        self,
        assignments: Iterable[TransactionAssignment],
        expected: set[TransactionStage],
        /,
        *,
        phase: str,
    ) -> None:
        invalid = [
            (
                assignment.transaction.id,
                assignment.transaction.stage,
            )
            for assignment in assignments
            if assignment.transaction.stage not in expected
        ]

        if not invalid:
            return

        details = ", ".join(
            f"{transaction_id}={stage}"
            for transaction_id, stage in invalid
        )

        raise RuntimeError(
            f"Invalid transaction stages after {phase}: {details}"
        )

    def validate_transactions(
        self,
        transactions: Sequence[Transaction],
        /,
    ) -> None:
        """
        - ensures not duplicates and that each transaction's stage is either
        CREATED or COMPLETED
        """
        seen_ids: set[str] = set()
        valid_start_stages = {
            TransactionStage.CREATED,
            TransactionStage.COMPLETED,
        }
        for txn in transactions:
            if txn.id in seen_ids:
                raise ValueError(
                    f"Duplicate transaction ID: "
                    f"{txn.id!r}"
                )
            seen_ids.add(txn.id)

            if txn.stage not in valid_start_stages:
                raise ValueError(
                    f"Transaction {txn.id!r} cannot be "
                    f"submitted from stage "
                    f"{txn.stage!s}"
                )
    
    @staticmethod
    def validate_bindings(
        bindings: Iterable[SessionBinding],
        /,
    ) -> None:
        """
        use to ensure two workers to not target same SAP session
        """
        seen: set[tuple[str, str]] = set()

        for binding in bindings:
            key = (
                binding.locator.connection_id,
                binding.locator.session_id,
            )

            if key in seen:
                raise ValueError(
                    "Duplicate SAP session binding: "
                    f"connection_id={key[0]!r}, "
                    f"session_id={key[1]!r}"
                )

            seen.add(key)
    
    @classmethod
    def from_locators(
        cls,
        locators: Iterable[SessionLocator],
        /,
        *,
        options: SessionPoolOptions | None = None,
        close_on_exit: bool = False,
    ) -> Self:
        return cls(
            Array.map(
                locators, 
                lambda loc: SessionBinding(loc, close_on_exit)
            ),
            options=options
        )
    
    def _require_started(self) -> None:
        """ validates that `self._closed is False` and `self._started is True`"""
        if self._closed:
            raise RuntimeError("SessionPool has been closed")

        if not self._started:
            raise RuntimeError(
                "SessionPool has not been started"
            )