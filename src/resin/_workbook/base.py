"""
*`@file`* `_workbook/base`
"""
from __future__ import annotations
from typing import Callable
import pythoncom, time, threading
from pywintypes import com_error
from contextlib import (contextmanager, ExitStack)
from pathlib import Path
from pyqi import (fs, dt, Array, export, Telemetry)
from lute import LogMsg, get_logger
from .types import (StagingPolicy, ControllerState)
from .base_options import (BaseControllerOptions, BaseControllerOptionsDict)
from .exceptions import (
    ConfigurationError, DeadSessionError, 
    WorkbookControllerError, WorkbookIOError
)
from resin.utils import runtime
from ._session_model import (SessionFactory, Session, default_session_factory)
from .deadline import (Deadline, cooldown_remaining)

mlog = get_logger(__file__)


class BaseController():
    def __init__(
        self,
        options: BaseControllerOptions | BaseControllerOptionsDict,
        session_factory: SessionFactory | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        pump: Callable[[], None] = runtime.pump_waiting_messages
    ):
        self.options = (
            BaseControllerOptions.from_dict(options) 
            if isinstance(options, dict) 
            else options
        )
        self._session_factory = session_factory or default_session_factory
        self._session: Session | None = None
        self._state = ControllerState.NEW
        self._clock, self._sleep, self._pump= clock, sleep, pump
        self._owner_thread: int | None = None
        self._stack: ExitStack | None = None

    @property
    def state(self): 
        return self._state

    def _check_thread(self) -> None:
        if (self._owner_thread is not None 
            and self._owner_thread != threading.get_ident()
        ):
            raise WorkbookControllerError("Controller used from a different thread")

    @property
    def session(self) -> Session:
        self._check_thread()
        if self._session is None or self._state not in {
            ControllerState.ENTERING, ControllerState.READY, ControllerState.CLOSING
        }:
            raise DeadSessionError("Controller has no usable Excel session")
        return self._session


    def deadline(self, seconds: float):
        return Deadline(
            seconds=seconds, 
            clock=self._clock, 
            sleep=self._sleep, 
            pump=self._pump,
            poll_seconds=self.options.poll_seconds
        )

    def __enter__(self):
        self._check_thread()
        if self._state != ControllerState.NEW:
            raise WorkbookControllerError("Controller objects are single-use")
        self._owner_thread = threading.get_ident()
        self._state = ControllerState.ENTERING
        stack = ExitStack()
        self._stack = stack