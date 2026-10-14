"""
*`@file`* `gui/models/transaction/enums`
"""
from __future__ import annotations
from enum import auto
from pyqi import (String, export)

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



class ExecutionType(String.BaseEnum):
    """
    ```
    STANDARD = auto()
    BACKGROUND = "async"
    ```
    """
    STANDARD = "standard_execution"
    ASYNC = "async_execution"

    # this might be something that some SAP super user sets up at company

__all__ = export(TransactionStage, ExecutionType)