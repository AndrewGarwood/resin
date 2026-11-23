"""
*`@file`* `utils/winauto/_application`
"""

from typing import Any
from pyqi import require, export
from .types import DesktopBackend
from pywinauto import (Application)
from .tools import get_backend_name


def connect(
    pid: int,
    /,
    *,
    backend: DesktopBackend | str | None=None,
    handle: int | None = None,
    path: str | None = None,
    timeout_seconds: float = 30.0
) -> Application:
    kwargs: dict[str, Any] = {
        "process": pid,
        "timeout": require.positive_number(timeout_seconds, "timeout_seconds")
    }
    if (handle is not None):
        kwargs["handle"] = handle
    if (path):
        kwargs["path"] = path
    return (
        Application(
            backend=(backend or get_backend_name())
        )
        .connect(**kwargs)
    )

__all__ = export(
    connect,
)