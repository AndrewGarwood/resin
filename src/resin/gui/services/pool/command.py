"""
*`@file`* `gui/services/pool/_command`
"""
from __future__ import annotations
from enum import auto
from dataclasses import dataclass
from pyqi import export, BaseStrEnum
from ..transaction import (Transaction)
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any


class SessionCommandType(BaseStrEnum):
    """
    ```
    PREPARE = auto()
    EXECUTE = auto()
    POST_EXECUTE = auto()
    EXPORT = auto()
    STOP = auto()
    ```
    """
    PREPARE = auto()
    EXECUTE = auto()
    POST_EXECUTE = auto()
    EXPORT = auto()
    STOP = auto()


@dataclass(slots=True)
class SessionCommand:
    type: SessionCommandType
    transaction: Transaction | None = None
    future: Future[Any] = field(default_factory=Future)


__all__ = export(SessionCommand, SessionCommandType)