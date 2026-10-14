"""
*`@file`* `gui/services/pool/session_binding`
"""
from enum import auto
from dataclasses import dataclass
from typing import (Any, Sequence, Protocol)
from pyqi import export
from concurrent.futures import Future, wait, ALL_COMPLETED

from resin.gui.com.gateway import ComGateway
from .assignment import TransactionAssignment
from .session_locator import SessionLocator
from resin.gui.core.session import (Session)

@dataclass(frozen=True, slots=True)
class SessionBinding:
    """
    Binds a SAP session identity to its pool ownership policy.

    close_on_exit=False:
        The session is borrowed. The worker must not close it.

    close_on_exit=True:
        The session is owned by the pool. The worker closes it before
        leaving its COM apartment.
    """

    locator: SessionLocator
    close_on_exit: bool = False

    @property
    def connection_id(self) -> str:
        return self.locator.connection_id

    @property
    def session_id(self) -> str:
        return self.locator.session_id

    def resolve(
        self,
        *,
        gateway: ComGateway | None = None,
    ) -> Session:
        return self.locator.resolve(gateway=gateway)

    def __call__(self) -> Session:
        return self.resolve()