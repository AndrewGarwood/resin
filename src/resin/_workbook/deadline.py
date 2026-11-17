"""
*`@file`* `_workbook/deadline`
"""

from __future__ import annotations

from datetime import datetime
# import re
import time
from typing import Callable
from pyqi import require, export
from lute import get_logger
from resin.utils import runtime
from .exceptions import ConfigurationError, RefreshTimeoutError

mlog = get_logger(__name__)

class Deadline:
    def __init__(
        self,
        seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        pump: Callable[[], object] = runtime.pump_waiting_messages,
        poll_seconds: float = 0.25,
    ) -> None:
        self.clock = clock
        self.sleep = sleep
        self.pump = pump
        self.poll_seconds = require.positive_number(poll_seconds, "poll_seconds")
        self.started = clock()
        self.expires = self.started + require.positive_number(seconds, "timeout_seconds")

    def remaining(self) -> float:
        remaining = self.expires - self.clock()
        if remaining <= 0:
            raise RefreshTimeoutError("Workbook operation deadline expired")
        return remaining

    def check(self, phase: str = "operation") -> None:
        try:
            self.remaining()
        except RefreshTimeoutError as error:
            error.add_context(phase=phase)
            raise

    def pause(self, seconds: float | None = None) -> None:
        interval = (
            self.poll_seconds 
            if seconds is None 
            else require.positive_number(
                seconds, "poll_seconds"
            )
        )
        self.pump()
        self.sleep(min(interval, self.remaining()))
        self.check()


def cooldown_remaining(
    previous: datetime | None,
    now: datetime,
    seconds: float,
    force: bool = False,
) -> float:
    """
    *`@returns`* cooldown remaining time in `seconds`
    - `0.0` if `previous is None` or `force==True`
    """
    cooldown = require.positive_number(seconds)
    if not isinstance(force, bool):
        raise ConfigurationError("force must be a boolean")
    if previous is None or force:
        return 0.0
    elapsed = (now - previous).total_seconds()
    if elapsed < 0:
        mlog.warning("Workbook refresh timestamp is in the future; clamping cooldown")
    return max(0.0, cooldown - max(0.0, elapsed))

__all__ = export(Deadline, cooldown_remaining)