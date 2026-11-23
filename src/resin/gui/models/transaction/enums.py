"""
*`@file`* `gui/models/transaction/enums`
"""
from __future__ import annotations
from enum import auto
from pyqi import (BaseStrEnum, export)

class TransactionStage(BaseStrEnum):
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



class ExecutionType(BaseStrEnum):
    """
    ```
    STANDARD = "standard"
    ASYNC = "async"
    ```
    """
    STANDARD = "standard"
    ASYNC = "async" # this might be something that some SAP super user sets up at company
    CUSTOM = "custom" # assigned by script when pass execute_fn to Transaction __init__
    

__all__ = export(TransactionStage, ExecutionType)