"""
*`@file`* `gui/com/runtime`

- moved content to `resin.utils.runtime`
"""
from __future__ import annotations
import pythoncom
from ..exceptions import SapComError
from lute import LogMsg

def pump_waiting_messages() -> None:
    """
    Process pending Windows COM messages for the current thread.

    The current thread must already have an initialized COM apartment.
    """
    try:
        pythoncom.PumpWaitingMessages()
    except Exception as e:
        raise SapComError(LogMsg.err(
            e,
            "Unable to pump pending COM messages",
        )) from e

__all__ = ["pump_waiting_messages"]