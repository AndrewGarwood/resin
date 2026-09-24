from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Self
import lute
from pyqi.validation import require
from win32com.client import CDispatch
from ..com.gateway import ComGateway
from ..com.types import DispatchLike
from ..config import AppManager
from ..context import SapContext
from ..exceptions import (
    SapComError,
    SapConnectionNotFoundError,
    SapGuiError,
)
from .connection import Connection


mlog = lute.get_logger(__file__)


class Application:
    """
    Wrapper around the SAP GUI scripting application.

    The wrapper does not retain the COM dispatch object. Each property or
    operation resolves the currently running SAP GUI scripting engine through
    ``ComGateway``.

    This makes the wrapper safer to retain across SAP GUI reconnects and
    prevents accidental sharing of a child COM dispatch object between COM
    apartments.
    """

    def __init__(
        self,
        *,
        gateway: ComGateway,
        context: SapContext | None = None,
    ) -> None:
        self._gateway = gateway

        if context is None:
            app_id = self._read_dispatch_id(gateway.get_application())
            context = SapContext(application_id=app_id)
        self._context = context

    @classmethod
    def attach(
        cls,
        /,
        gateway: ComGateway | None = None,
    ) -> Self:
        """
        Attach to the currently running SAP GUI scripting engine.

        The calling thread must have an initialized COM apartment. Worker
        threads should use ``ComGateway.com_apartment()``.
        """
        gateway = gateway or ComGateway()
        app = gateway.get_application()
        return cls(
            gateway=gateway,
            context=SapContext(application_id=cls._read_dispatch_id(app)),
        )

    @property
    def gateway(self) -> ComGateway:
        return self._gateway

    @property
    def context(self) -> SapContext:
        return self._context

    @property
    def id(self) -> str:
        """
        Return the SAP GUI application's runtime ID.

        If no application ID was recorded when the wrapper was constructed,
        resolve the current application's ID.
        """
        if self._context.application_id is not None:
            return self._context.application_id

        return self._read_dispatch_id(self._com)

    @property
    def _com(self) -> DispatchLike:
        return self._gateway.get_application()

    @property
    def connections(self) -> tuple[Connection, ...]:
        """
        Return a snapshot of currently open SAP GUI connections.
        """
        app = self._com
        try:
            children = app.Children
            count = int(children.Count)
        except Exception as e:
            raise SapComError("Unable to enumerate SAP GUI connections") from e

        result: list[Connection] = []
        for index in range(count):
            try:
                conn_com = children(index)
                connection_id = str(conn_com.Id)
                sap_type = str(conn_com.Type)
            except Exception as e:
                raise SapComError(
                    f"Unable to inspect SAP GUI application child "
                    f"at index {index}"
                ) from e

            if sap_type != "GuiConnection":
                raise SapComError(
                    f"SAP GUI application child {index} reported type "
                    f"{sap_type!r}; expected 'GuiConnection'"
                )

            result.append(
                Connection(
                    gateway=self._gateway,
                    context=self._context.with_connection(connection_id),
                )
            )

        return tuple(result)

    @property
    def connection_count(self) -> int:
        return len(self.connections)

    @property
    def total_session_count(self) -> int:
        return sum(
            connection.session_count
            for connection in self.connections
        )

    @property
    def session_capacity(self) -> int:
        return AppManager.session_capacity()

    @property
    def has_session_capacity(self) -> bool:
        return self.total_session_count < self.session_capacity

    def assert_session_capacity(
        self,
        *,
        limit: int | None = None,
    ) -> None:
        actual_limit = (
            AppManager.session_capacity()
            if limit is None
            else limit
        )
        if actual_limit < 1:
            raise ValueError("limit must be at least 1")
        current = self.total_session_count
        if current >= actual_limit:
            raise SapGuiError(
                "Cannot create another SAP GUI session because the "
                f"application session limit has been reached: "
                f"current={current}, limit={actual_limit}"
            )

    def get_connection(
        self,
        index: int = 0,
        /,
    ) -> Connection:
        """
        Return an open connection by snapshot index.
        """
        connections = self.connections
        try:
            return connections[index]
        except IndexError as e:
            raise IndexError(
                f"SAP GUI connection index out of range: index={index}, "
                f"count={len(connections)}"
            ) from e

    def find_connection(
        self,
        *,
        connection_id: Optional[str] = None,
        description: Optional[str] = None,
        runtime_name: Optional[str] = None,
        runtime_id: Optional[str] = None,
        connection_string: Optional[str] = None,
    ) -> Connection | None:
        """
        Find an already-open connection.

        Every non-None criterion must match. Property-read failures are treated
        as non-matches for that connection because some SAP GUI versions may
        not expose every optional connection property.
        """
        criteria = {
            "connection_id": connection_id,
            "description": description,
            "runtime_name": runtime_name,
            "runtime_id": runtime_id,
            "connection_string": connection_string,
        }

        provided = {
            name: value
            for name, value in criteria.items()
            if value is not None
        }

        if not provided:
            raise ValueError(
                "At least one connection search criterion is required"
            )

        for connection in self.connections:
            matches: bool = True
            for name, expected in provided.items():
                try:
                    if name == "connection_id":
                        actual = connection.id
                    else:
                        actual = getattr(connection, name)
                except (AttributeError, SapComError):
                    matches = False
                    break
                if actual != expected:
                    matches = False
                    break
            if matches:
                return connection
        return None

    def require_connection(
        self,
        *,
        connection_id: Optional[str] = None,
        description: Optional[str] = None,
        runtime_name: Optional[str] = None,
        runtime_id: Optional[str] = None,
        connection_string: Optional[str] = None,
    ) -> Connection:
        connection = self.find_connection(
            connection_id=connection_id,
            description=description,
            runtime_name=runtime_name,
            runtime_id=runtime_id,
            connection_string=connection_string,
        )

        if connection is None:
            supplied = {
                name: value
                for name, value in {
                    "connection_id": connection_id,
                    "description": description,
                    "runtime_name": runtime_name,
                    "runtime_id": runtime_id,
                    "connection_string": connection_string,
                }.items()
                if value is not None
            }

            raise SapConnectionNotFoundError(
                f"No open SAP GUI connection matched {supplied!r}"
            )

        return connection

    def open_connection(
        self,
        description: str,
        /,
        *,
        sync: bool = True,
        raise_on_error: bool = True,
        enforce_session_capacity: bool = True,
    ) -> Connection:
        """
        Open a connection using its SAP Logon description.
        """
        require.non_empty_string(
            description,
            name="description",
        )

        if enforce_session_capacity:
            self.assert_session_capacity()

        application = self._com

        try:
            dispatch = application.OpenConnection(
                description,
                sync,
                raise_on_error,
            )
        except Exception as e:
            raise SapComError(
                f"Unable to open SAP GUI connection with description "
                f"{description!r}"
            ) from e

        connection_id = self._validate_connection_dispatch(dispatch)
        return Connection(
            gateway=self._gateway,
            context=self._context.with_connection(connection_id),
        )

    def open_connection_by_string(
        self,
        connection_string: str,
        /,
        *,
        synchronous: bool = True,
        raise_on_error: bool = True,
        enforce_session_capacity: bool = True,
    ) -> Connection:
        """
        Open a connection using a technical SAP connection string.

        Example:
            /R/PN1/G/PUBLIC
        """
        require.non_empty_string(
            connection_string,
            name="connection_string",
        )

        if enforce_session_capacity: self.assert_session_capacity()
        app = self._com

        try:
            dispatch = app.OpenConnectionByConnectionString(
                connection_string,
                synchronous,
                raise_on_error,
            )
        except Exception as e:
            raise SapComError(
                "Unable to open SAP GUI connection using connection "
                f"string {connection_string!r}"
            ) from e

        connection_id = self._validate_connection_dispatch(dispatch)

        return Connection(
            gateway=self._gateway,
            context=self._context.with_connection(connection_id),
        )

    def refresh(self) -> Self:
        """
        Verify that SAP GUI and the scripting engine remain available.
        """
        application = self._com
        application_id = self._read_dispatch_id(application)

        self._context = SapContext(
            application_id=application_id,
        )

        return self

    @staticmethod
    def _validate_connection_dispatch(dispatch: CDispatch,/,) -> str:
        if dispatch is None:
            raise SapComError(f"returned None")
        try:
            connection_id = str(dispatch.Id)
            sap_type = str(dispatch.Type)
        except Exception as e:
            raise SapComError(
                f"returned an incompatible object"
            ) from e

        if sap_type != "GuiConnection":
            raise SapComError(
                f"returned SAP type {sap_type!r}; "
                "expected 'GuiConnection'"
            )
        if not connection_id:
            raise SapComError(
                f"returned an empty connection ID"
            )
        return connection_id

    @staticmethod
    def _read_dispatch_id(dispatch: Any,/) -> str:
        return ComGateway.get_property(
            dispatch, 
            "Id", 
            str, 
            source="Application._read_dispatch_id", 
            _raise=True
        )

    def __repr__(self) -> str:
        return f"<Application id={self.id!r}>"
