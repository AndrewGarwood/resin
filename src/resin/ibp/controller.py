"""
*`@file`* `ibp/controller`
"""
from __future__ import annotations
from dataclasses import dataclass
import shutil, threading, time, warnings
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from lute import LogMsg
from resin.utils import winauto
from resin._workbook import (
    ConnectionBindingError, ConfigurationError, BaseController, Deadline, BaseControllerOptions,
    RefreshOutcome, RefreshStatus, SessionFactory, StagingPolicy, 
    cooldown_remaining, parse_refresh_timestamp
)

from .connection_options import (ConnectionOptions)
from .workbook_options import (WorkbookOptions)
from ._options import (ControllerOptions, ControllerOptionsDict)


class Controller(BaseController):
    def __init__(
        self,
        options: str | Path | ControllerOptions | ControllerOptionsDict
    ):
        self.options = (
            options if isinstance(options, ControllerOptions) 
            else ControllerOptions.from_config(options)
        )