"""
*`@file`* `resin/gui/utils/concurrency`
"""

import time
import threading
import pythoncom
from functools import wraps
from typing import Any, Callable, TypeVar, ParamSpec, Concatenate
from lute import LogMsg, annotate

P = ParamSpec("P")
R = TypeVar("R")
TObj = TypeVar("TObj")

_SESSION_LOCKS: dict[str, threading.RLock] = {}
_SESSION_LOCKS_GUARD = threading.RLock()

def thread_alias() -> str:
    """ *`@returns`* `threading.current_thread().name.split("-")[1]` """
    return threading.current_thread().name.split("-")[1]

thread_id = thread_alias # temp during refactor

def _session_key(session: Any, /) -> str:
    conn_id = getattr(session, "_conn_id", None)
    session_id = getattr(session, "_session_id", None)
    if (not conn_id or not session_id):
        raise RuntimeError(f"Cannot build SAP session lock key. {conn_id=}, {session_id=}")
    return f"{conn_id}:{session_id}"


def _get_session_lock(session: Any, /) -> threading.RLock:
    key = _session_key(session)
    with _SESSION_LOCKS_GUARD:
        lock = _SESSION_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _SESSION_LOCKS[key] = lock
        return lock

def wait_for_session_idle(session: Any, /, timeout: float = 60.0, poll: float = 0.05) -> None:
    start = time.time()
    if (not hasattr(session, "busy")):
        raise ValueError(LogMsg(
            f"Invalid session instance",
            session=annotate(session)
        ))
    while session.busy:
        if (time.time() - start > timeout):
            raise TimeoutError("SAP session remained busy too long")
        time.sleep(poll)

def _pump_wait(seconds: float, /) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try: 
            pythoncom.PumpWaitingMessages()
        except Exception: 
            pass
        time.sleep(0.01)


def busy_safe(
    wait_before: bool = True, 
    wait_after: bool = False
) -> Callable[
    [Callable[Concatenate[TObj, P], R]], Callable[Concatenate[TObj, P], R]
]:
    def decorator_busy_safe(
        method: Callable[Concatenate[TObj, P], R]
    ) -> Callable[Concatenate[TObj, P], R]:
        @wraps(method)
        def wrapper(self: TObj, *args: P.args, **kwargs: P.kwargs) -> R:
            session = getattr(self, "session", None)
            if session is None:
                raise RuntimeError(
                    f"{type(self).__name__}.{method.__name__} missing session"
                )
            lock = _get_session_lock(session)
            with lock:
                try:
                    if wait_before: wait_for_session_idle(session)
                    _pump_wait(0.03)
                    result = method(self, *args, **kwargs)
                    _pump_wait(0.03)
                    if wait_after: wait_for_session_idle(session)
                    return result
                except Exception as e:
                    raise RuntimeError(LogMsg.err(
                        e,
                        f"[busy_safe] SAP GUI call failed.",
                    )) from e
        return wrapper
    return decorator_busy_safe