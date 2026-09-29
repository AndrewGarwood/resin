"""
*`@file`* `gui/models/transaction/_transaction`
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from threading import Condition, RLock
from enum import auto
from pyqi import (String, export)
from pyqi.fs import (StrPath)
from pyqi.models import (Flow, StageTransition)

import lute
LogMsg = lute.LogMsg
mlog = lute.get_logger(Path(__file__).parent.stem)

class TransactionStage(String.BaseEnum):
    """
    ```
    CREATED = auto()
    OPENING = auto()
    POPULATING_SELECTION = auto()
    READY_TO_EXECUTE = auto()
    DISPATCHING_EXECUTE = auto()
    EXECUTION_RUNNING = auto()
    POST_EXECUTE = auto()
    READY_TO_EXPORT = auto()
    EXPORTING = auto()
    COMPLETED = auto()
    FAILED = auto()
    ```
    """
    CREATED = auto()
    OPENING = auto()
    POPULATING_SELECTION = auto()
    READY_TO_EXECUTE = auto()

    DISPATCHING_EXECUTE = auto()
    EXECUTION_RUNNING = auto()
    POST_EXECUTE = auto()

    READY_TO_EXPORT = auto()
    EXPORTING = auto()

    COMPLETED = auto()
    FAILED = auto()