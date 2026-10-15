"""
*`@file`* `gui/services/pool/waiters`
"""
from collections.abc import Iterable
from .types import (PendingCommand)
from .exceptions import (SessionPoolError)

from collections.abc import Iterable
from concurrent.futures import wait, ALL_COMPLETED

def wait_for_commands(
    pending: Iterable[PendingCommand],
    /,
    *,
    timeout: float | None,
) -> None:
    commands = tuple(pending)
    futures = tuple(item.future for item in commands)

    done, not_done = wait(
        futures,
        timeout=timeout,
        return_when=ALL_COMPLETED,
    )

    if not_done:
        unfinished = [
            item.assignment.transaction.id
            for item in commands
            if item.future in not_done
        ]
        raise TimeoutError(
            "Session-pool phase did not complete; "
            f"unfinished transactions={unfinished!r}"
        )

    errors: list[tuple[str, BaseException]] = []

    for item in commands:
        error = item.future.exception()
        if error is not None:
            errors.append(
                (
                    item.assignment.transaction.id,
                    error,
                )
            )

    if errors:
        formatted = ", ".join(
            f"{transaction_id}: {error}"
            for transaction_id, error in errors
        )
        raise SessionPoolError(
            f"One or more worker commands failed: {formatted}",
            errors=errors,
        )