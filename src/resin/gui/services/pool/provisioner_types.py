"""
*`@file`* `gui/services/pool/provisioner_types`
"""
from __future__ import annotations
from typing import (Any, Self, TypedDict, Required)
from dataclasses import dataclass, field
from pyqi import Json, require, export
from lute import LogMsg
from resin.gui.models.connection_options import (
    ConnectionOptions, ConnectionOptionsDict
)
from .connection import (ConnectionLease)

from .session_binding import SessionBinding


class SessionProvisionerOptionsDict(TypedDict, total=False):
    session_count: Required[int]

    connection: ConnectionOptionsDict

    launch_if_unavailable: bool

    attach_timeout: float
    attach_poll_interval: float

    create_timeout: float
    create_poll_interval: float

    close_created_sessions_on_exit: bool
    close_opened_connection_on_exit: bool


@dataclass(frozen=True, slots=True)
class SessionProvisionerOptions(Json.Serial[SessionProvisionerOptionsDict]):
    """
    *`@extends`* `Serial[SessionProvisionerOptionsDict]`
    ```
    session_count: int = 1
    connection: ConnectionOptions = field(default_factory=ConnectionOptions)
    launch_if_unavailable: bool = False
    attach_timeout: float = 30.0
    attach_poll_interval: float = 0.25
    create_timeout: float = 15.0
    create_poll_interval: float = 0.1
    close_created_sessions_on_exit: bool = True
    close_opened_connection_on_exit: bool = False
    ```
    """
    session_count: int = 1

    connection: ConnectionOptions = field(default_factory=ConnectionOptions)

    launch_if_unavailable: bool = True

    attach_timeout: float = 30.0
    attach_poll_interval: float = 0.25

    create_timeout: float = 15.0
    create_poll_interval: float = 0.1

    close_created_sessions_on_exit: bool = True
    close_opened_connection_on_exit: bool = True

    def __post_init__(self) -> None:
        label = self.__attr_label__
        require.positive_integer(
            self.session_count, 
            label("session_count")
        )
        # require.non_negative_integer(
        #     self.connection_index, 
        #     label("connection_index")
        # )
        require.positive_number(
            self.attach_timeout, 
            label("attach_timeout")
        )
        require.positive_number(
            self.attach_poll_interval, 
            label("attach_poll_interval")
        )
        require.positive_number(
            self.create_timeout, 
            label("create_timeout")
        )
        require.positive_number(
            self.create_poll_interval, 
            label("create_poll_interval")
        )
        unable_to_select_connection = (
            self.connection.index is None 
            and all(selector is None for selector in (
                self.connection.id,
                self.connection.description,
                self.connection.string,
            ))
        )
        if (unable_to_select_connection):
            raise ValueError(LogMsg(
                f"Invalid SessionProvisionerOptions (constructor)",
                f"When connection.index not provided, must provide one of:",
                f"connection.id, connection.description, connection.string"
            ))

    @classmethod
    def from_dict(
        cls, 
        data: SessionProvisionerOptionsDict | dict[str, Any], 
        /
    ) -> Self:
        try:
            conn_options_val = data.get('connection', None)
            conn: ConnectionOptions | None = None
            if (conn_options_val):
                if (not isinstance(conn_options_val, dict)):
                    raise TypeError(LogMsg.bad_arg(
                        conn_options_val, 
                        f"SessionProvisionerOptionsDict['connection']", 
                        "Invalid value for connection", 
                        ConnectionOptionsDict, type(None) 
                    ))
                conn = ConnectionOptions.from_dict(conn_options_val)
            return cls(
                session_count=data['session_count'],
                connection=conn or ConnectionOptions(),
                launch_if_unavailable=data.get('launch_if_unavailable', True),
                attach_timeout=data.get('attach_timeout', 30.0),
                attach_poll_interval=data.get('attach_poll_interval', 0.25),
                create_timeout=data.get('create_timeout', 15.0),
                create_poll_interval=data.get('create_poll_interval', 0.1),
                close_created_sessions_on_exit=data.get('close_created_sessions_on_exit', True),
                close_opened_connection_on_exit=data.get('close_opened_connection_on_exit', True),
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                received=Json.serialize(data)
            )) from e


@dataclass(frozen=True, slots=True)
class SessionProvisioningResult:
    """
    *`@property`* `def session_count(self) -> int`
    """
    bindings: tuple[SessionBinding, ...]
    connection: ConnectionLease

    reused_session_count: int
    created_session_count: int

    launched_application: bool = False

    @property
    def session_count(self) -> int:
        return len(self.bindings)

    @property
    def connection_id(self): 
        return self.connection.locator.connection_id
    
    @property
    def application_id(self): 
        return self.connection.locator.application_id
    @property
    def opened_connection(self) -> bool:
        return self.connection.close_on_exit

__all__ = export(
    SessionProvisionerOptionsDict, 
    SessionProvisionerOptions, 
    SessionProvisioningResult
)