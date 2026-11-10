"""
*`@file`* `_workbook/_session_model`
"""

from pathlib import Path
from pyqi import export
from typing import (Protocol, TypeAlias, Callable, Any, Self)

class Session(Protocol):
    @property
    def excel(self) -> Any: ...

    @property
    def pid(self) -> int: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool: ...

    def get_com_addin(self, name: str, /) -> Any: ...

    def open_workbook(self, path: Path, /) -> Any: ...

    def add_workbook(self, path: Path, /) -> Any: ...

    def save_workbook(self, wb: Any, /, timeout: float = 20.0) -> None: ...

    def close_workbook(
        self, wb: Any, /, save_changes: bool = False
    ) -> None: ...


SessionFactory: TypeAlias = Callable[[], Session]

def default_session_factory():
    from noxl.engines.xlcom.session import ExcelSession
    return ExcelSession(
        visible=True, 
        display_alerts=True,
        screen_updating=True,
        enable_events=True,
        kill_on_exit=True
    )


__all__ = export(Session, "SessionFactory", default_session_factory)