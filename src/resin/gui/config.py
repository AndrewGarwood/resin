"""
*`@file`* `resin/gui/config.py`
"""
from __future__ import annotations
from pathlib import Path
from typing import Final


SAPGUI_OBJECT_ID = "SAPGUI"
CONN_SESSION_LIMIT: Final[int] = 6
APP_SESSION_LIMIT: Final[int] = 6
DEFAULT_EXE_PATH = "C:/Program Files (x86)/SAP/FrontEnd/SAPgui/saplogon.exe"
# TODO: different default exe path based on operating system (windows, linux, mac, etc.)

class AppManager():
    """ `ApplicationManager` """
    _connection_session_capacity: int = CONN_SESSION_LIMIT
    _total_session_capacity: int = APP_SESSION_LIMIT
    _exe_path = DEFAULT_EXE_PATH
    _strict: bool = True
    _verbose: bool = False

    @classmethod
    def is_verbose(cls):
        return cls._verbose
    @classmethod
    def set_verbose(cls, value: bool, /):
        if not isinstance(value, bool):
            raise ValueError(f"verbose must be a boolean, got {type(value)}")
        cls._verbose = value

    @classmethod
    def is_strict(cls) -> bool:
        return cls._strict
    @classmethod
    def set_strict(cls, value: bool, /):
        if not isinstance(value, bool):
            raise ValueError(f"strict must be a boolean, got {type(value)}")
        cls._strict = value
    
    @classmethod
    def exe(cls) -> str:
        return cls._exe_path
    @classmethod
    def set_exe(cls, value: str | Path, /):
        cls._exe_path = str(value)

    @classmethod
    def exe_path(cls):
        """ `=Path(cls.exe_str)` """
        return Path(cls.exe())

    @classmethod
    def session_capacity(cls) -> int:
        """ total number of sessions across all open conncetions. `default=6`"""
        return cls._total_session_capacity
    @classmethod
    def set_session_capacity(cls, value: int, /):
        if value < 1:
            raise ValueError("session_capacity must be >= 1")
        if (cls.is_strict() and value > APP_SESSION_LIMIT):
            raise ValueError(
                f"(strict) session_capacity cannot exceed {APP_SESSION_LIMIT=}"
                )
        cls._total_session_capacity = value
    @classmethod
    def connection_session_capacity(cls) -> int:
        """ i.e. max sessions per connection"""
        return cls._connection_session_capacity
    @classmethod
    def set_connection_session_capacity(cls, value: int, /):
        if value < 1:
            raise ValueError("connection_session_capacity must be >= 1")
        if (cls.is_strict() and value > CONN_SESSION_LIMIT):
            raise ValueError(f"(strict) connection_session_capacity cannot exceed {CONN_SESSION_LIMIT=}")
        cls._connection_session_capacity = value