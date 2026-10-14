"""
*`@file`* `gui/services/pool/types`
"""
from enum import auto
from dataclasses import dataclass
from typing import (Any, Sequence, Protocol)
from pyqi import export
from concurrent.futures import Future, wait, ALL_COMPLETED
from .assignment import TransactionAssignment
from .session_locator import SessionLocator
from resin.gui.core.session import (Session)


@dataclass(frozen=True, slots=True)
class PendingCommand:
    assignment: TransactionAssignment
    future: Future[Any]

class SessionProvider(Protocol):
    def __call__(self) -> Session: ...
