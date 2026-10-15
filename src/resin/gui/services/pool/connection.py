"""
*`@file`* `gui/services/pool/connection`
"""
from __future__ import annotations

from dataclasses import dataclass

from pyqi import require, export

from resin.gui.com.gateway import ComGateway
from resin.gui.context import SapContext
from resin.gui.core.connection import Connection

@dataclass(frozen=True, slots=True)
class ConnectionLocator:
    """
    Immutable identity for an existing SAP GUI connection.

    Contains no resolved COM dispatch objects.
    """

    connection_id: str
    application_id: str | None = None

    def __post_init__(self) -> None:
        require.non_empty_string(
            self.connection_id,
            "connection_id",
        )

        if self.application_id is not None:
            require.non_empty_string(
                self.application_id,
                "application_id",
            )

    def resolve(
        self,
        *,
        gateway: ComGateway | None = None,
    ) -> Connection:
        return Connection(
            gateway=gateway or ComGateway(),
            context=SapContext(
                application_id=self.application_id,
                connection_id=self.connection_id,
            ),
        )

    def __call__(
        self,
        *,
        gateway: ComGateway | None = None,
    ) -> Connection:
        return self.resolve(gateway=gateway)


@dataclass(frozen=True, slots=True)
class ConnectionLease:
    """
    Connection identity and cleanup ownership.

    close_on_exit=True means the provisioner opened this connection
    specifically for the pool, so the pool closes it after stopping
    every worker.

    close_on_exit=False means the connection was borrowed.
    """

    locator: ConnectionLocator
    close_on_exit: bool = False

__all__ = export(ConnectionLocator, ConnectionLease)