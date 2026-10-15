"""
*`@file`* `gui/services/pool/types`
"""
from dataclasses import dataclass
from typing import (Any, Protocol)
from pyqi import export
from concurrent.futures import Future
from .assignment import TransactionAssignment
from resin.gui.core import (Application, Connection)


@dataclass(frozen=True, slots=True)
class PendingCommand:
    assignment: TransactionAssignment
    future: Future[Any]

class SapGuiLauncher(Protocol):
    """`Protocol` - callable that launches SAPGUI exe """
    def __call__(self) -> None:
        ...

class ConnectionBootstrapper(Protocol):
    """ `Protocol` - callable that accepts `Application` arg and returns `Connection` """
    def __call__(
        self,
        application: Application,
    ) -> Connection:
        ...

class ApplicationFactory(Protocol):
    """`Protocol` - callable that returns `Application` """
    def __call__(self) -> Application: ...


__all__ = export(
    PendingCommand, 
    SapGuiLauncher,
    ConnectionBootstrapper, 
    ApplicationFactory
)
