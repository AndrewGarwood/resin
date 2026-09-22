"""
*`@file`* `resin/gui/config.py`
"""
from __future__ import annotations
from typing import Final
import lute


MAX_SESSIONS_PER_CONNECTION: Final[int] = 6
MAX_SESSIONS_TOTAL: Final[int] = 6
DEFAULT_EXE_PATH = "C:/Program Files (x86)/SAP/FrontEnd/SAPgui/saplogon.exe"

class AppManager():
    """ `ApplicationManager` """
    _sessions_per_connection: int = MAX_SESSIONS_PER_CONNECTION
    _sessions_total: int = MAX_SESSIONS_TOTAL
    _exe_path = DEFAULT_EXE_PATH