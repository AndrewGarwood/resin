from __future__ import annotations

from contextlib import contextmanager
from typing import (Any, Callable, Generator, Literal, TypeVar, overload)
import time
import pythoncom
from pyqi import export
from pyqi.validation import require
from ..exceptions import SapComError


import lute
LogMsg = lute.LogMsg
mlog = lute.get_logger(__file__)


T = TypeVar("T")

@contextmanager
def com_apartment() -> Generator[None]:
    """ 
    context manager that handles 
    `pythoncom.CoInitialize()` and `pythoncom.CoUninitialize()`
    """
    pythoncom.CoInitialize()
    try:
        yield
    finally:
        pythoncom.CoUninitialize()


def pump_waiting_messages() -> None:
    """
    Process pending Windows COM messages for the current thread.

    The current thread must already have an initialized COM apartment.
    """
    try:
        pythoncom.PumpWaitingMessages()
    except Exception as e:
        raise SapComError(
            LogMsg.err(
                e,
                "Unable to pump pending COM messages",
            )
        ) from e


def try_pump_waiting_messages() -> bool:
    try:
        pythoncom.PumpWaitingMessages()
        return True
    except Exception as e:
        mlog.debug(
            LogMsg.err(
                e,
                "Unable to pump pending COM messages",
            )
        )
        return False



def validate_polling(
    timeout: float,
    poll_interval: float,
) -> tuple[float, float]:
    checked_timeout = float(
        require.positive_number(
            timeout,
            name="timeout",
        )
    )
    checked_poll_interval = float(
        require.positive_number(
            poll_interval,
            name="poll_interval",
        )
    )

    return (checked_timeout, checked_poll_interval)

@overload
def poll_until(
    operation: Callable[[], T | None],
    *,
    timeout: float,
    poll_interval: float,
    description: str,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    _raise: Literal[True]=True
) -> T: ...

@overload
def poll_until(
    operation: Callable[[], T | None],
    *,
    timeout: float,
    poll_interval: float,
    description: str,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    _raise: Literal[False]=False
) -> T | None: ...

def poll_until(
    operation: Callable[[], T | None],
    *,
    timeout: float,
    poll_interval: float,
    description: str,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    _raise: bool=True
) -> Any:
    timeout, poll_interval = validate_polling(
        timeout=timeout,
        poll_interval=poll_interval,
    )

    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    _MISSING = object()
    while True:
        try:
            result = operation()
            if result is not _MISSING:
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
            if (not _raise):
                mlog.warning(LogMsg.err(error))
                return None
            if (last_error is not None):
                raise error from last_error
            raise error

        try_pump_waiting_messages()
        time.sleep(min(poll_interval, remaining))

__all__ = export(
    poll_until, 
    validate_polling, 
    try_pump_waiting_messages, 
    pump_waiting_messages, 
    com_apartment
)