"""
*`@file`* `utils/winauto/window/_process`
"""
from resin.utils.winauto.types import (DesktopBackend)
from .options import WindowCriteria
from ._find import (find as find_window)
from ..application import connect
from resin.utils.winauto.tools import get_backend_name
from pywinauto import Application
from pywinauto.base_wrapper import BaseWrapper

def attach_process(
    pid: int, 
    criteria: WindowCriteria,
    /,
    *,
    backend: DesktopBackend | str | None=None, 
    require_unique: bool=True,
    timeout_seconds: float=30.0,
) -> tuple[Application, BaseWrapper]:
    app = connect(
        pid, 
        backend=(backend or get_backend_name()), 
        timeout_seconds=timeout_seconds
    )
    window = find_window(
        criteria, 
        app=app, 
        require_unique=require_unique, 
        strict=True
    )
    return (app, window)

__all__ = [
    "attach_process",
]