from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

import lute
import pythoncom

from ..utils.types import (require_positive_number)
from ..exceptions import SapComError


LogMsg = lute.LogMsg
mlog = lute.get_logger(__file__)


@contextmanager
def com_apartment() -> Generator[None]:
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
        require_positive_number(
            timeout,
            name="timeout",
        )
    )
    checked_poll_interval = float(
        require_positive_number(
            poll_interval,
            name="poll_interval",
        )
    )

    return (checked_timeout, checked_poll_interval)