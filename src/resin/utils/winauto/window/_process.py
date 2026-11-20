"""
*`@file`* `utils/winauto/window/_process`
"""
from resin.utils.winauto.types import (DesktopBackend)
from ._legacy import (find_window_by_title)
from pywinauto import Application
from pywinauto.backend import name as get_backend_name
from pywinauto.base_wrapper import BaseWrapper

def attach_process(
    pid: int, 
    title: str, 
    /,
    backend: DesktopBackend | str | None=None, 
    require_unique: bool=True,
    ignore_case: bool=True,
    timeout_seconds: float=30.0,
) -> tuple[Application, BaseWrapper]:
    if (not backend):
        backend = str(get_backend_name())
    print(f"{str(backend)=}")
    app = (
        Application(backend=backend)
        .connect(
            process=pid,
            timeout=timeout_seconds
        )
    )
    print(f"{str(app.windows())=}")
    window = find_window_by_title(
        app, 
        title, 
        require_unique=require_unique, 
        ignore_case=ignore_case
    )
    return (app, window)

__all__ = [
    "attach_process",
]