"""
*`@file`* `resin/gui/utils/waits`
- explicit waits for idle sessions, windows, and components.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

import lute

from ..com.runtime import (try_pump_waiting_messages, validate_polling)


LogMsg = lute.LogMsg

T = TypeVar("T")


def poll_until(
    operation: Callable[[], T | None],
    *,
    timeout: float,
    poll_interval: float,
    description: str,
    retry_on: tuple[type[Exception], ...] = (Exception,),
) -> T:
    timeout, poll_interval = validate_polling(
        timeout=timeout,
        poll_interval=poll_interval,
    )

    deadline = time.monotonic() + timeout
    last_error: Exception | None = None

    while True:
        try:
            result = operation()
            if result is not None:
                return result
        except retry_on as e:
            last_error = e

        remaining = deadline - time.monotonic()

        if remaining <= 0:
            error = TimeoutError(
                LogMsg(
                    f"Timed out waiting for {description}",
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
            )

            if last_error is not None:
                raise error from last_error
            raise error

        try_pump_waiting_messages()
        time.sleep(min(poll_interval, remaining))