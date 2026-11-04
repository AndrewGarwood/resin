"""Cooperative deadlines and workbook timestamp normalization."""
from __future__ import annotations

from datetime import datetime, timedelta
import re
import time
from typing import Any, Callable

import pythoncom
from lute import get_logger

from .models import ConfigurationError, RefreshTimeoutError, validate_duration

logger = get_logger(__name__)
_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


class Deadline:
    def __init__(
        self,
        seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        pump: Callable[[], object] = pythoncom.PumpWaitingMessages,
        poll_seconds: float = 0.25,
    ) -> None:
        self.clock = clock
        self.sleep = sleep
        self.pump = pump
        self.poll_seconds = validate_duration(poll_seconds, "poll_seconds")
        self.started = clock()
        self.expires = self.started + validate_duration(seconds, "timeout_seconds")

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
        interval = self.poll_seconds if seconds is None else validate_duration(
            seconds, "poll_seconds", allow_zero=True
        )
        self.pump()
        self.sleep(min(interval, self.remaining()))
        self.check()


def cooldown_remaining(
    previous: datetime | None,
    now: datetime,
    minutes: float,
    force: bool = False,
) -> float:
    cooldown = validate_duration(minutes, "cooldown_minutes", allow_zero=True) * 60
    if not isinstance(force, bool):
        raise ConfigurationError("force must be a boolean")
    if previous is None or force:
        return 0.0
    elapsed = (now - previous).total_seconds()
    if elapsed < 0:
        logger.warning("Workbook refresh timestamp is in the future; clamping cooldown")
    return max(0.0, cooldown - max(0.0, elapsed))


def parse_refresh_timestamp(
    value: object, *, date1904: bool = False
) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            raise ConfigurationError("Expected an unzoned workbook refresh timestamp")
        return value
    if isinstance(value, str):
        literal = value.strip()
        if literal.startswith("="):
            literal = literal[1:].strip()
        if literal.startswith('"') and literal.endswith('"'):
            literal = literal[1:-1]
        if not _NUMBER.fullmatch(literal):
            raise ConfigurationError("Invalid workbook refresh timestamp literal")
        value = float(literal)
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ConfigurationError("Expected an Excel serial refresh timestamp")
    serial = validate_duration(value, "refresh timestamp", allow_zero=True)
    if serial == 0:
        return None
    # Excel's 1900 system includes the fictitious 1900-02-29.
    epoch = datetime(1904, 1, 1) if date1904 else datetime(1899, 12, 30)
    if not date1904 and serial < 60:
        serial += 1
    try:
        return epoch + timedelta(days=serial)
    except OverflowError as error:
        raise ConfigurationError("Excel refresh timestamp is out of range") from error


def read_workbook_name(
    wb: Any, name: str, *, missing_ok: bool = False
) -> object:
    """Read constants directly; access RefersToRange only for nonconstant names."""
    if missing_ok:
        candidates = [
            item for item in wb.Names
            if str(item.Name).split("!")[-1].casefold() == name.casefold()
        ]
        if not candidates:
            return None
        if len(candidates) != 1:
            raise ConfigurationError(f"Ambiguous workbook name: {name}")
        entry = candidates[0]
    else:
        entry = wb.Names(name)
    formula = str(entry.RefersTo)
    if formula.startswith("="):
        literal = formula[1:]
        if _NUMBER.fullmatch(literal.strip()):
            return float(literal)
        if re.fullmatch(r'"(?:[^"]|"")*"', literal):
            return literal[1:-1].replace('""', '"')
    return entry.RefersToRange.Value
