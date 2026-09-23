from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional, Self

import pythoncom

from ..com.gateway import ComGateway
from ..com.types import DispatchLike
from ..config import AppManager
from ..context import SapContext
from ..exceptions import (
    SapComError,
    SapGuiError,
    SapSessionNotFoundError,
)

if TYPE_CHECKING:
    from .application import Application
    from .session import Session


class Connection:
    """
    Wrapper around an open SAP GUI connection.

    A connection is identified by its SAP runtime ID, for example:

        /app/con[0]
    """

    def __init__(
        self,
        *,
        gateway: ComGateway,
        context: SapContext,
        session_capacity: Optional[int] = None,
    ) -> None:
        context.require_connection()

        if context.session_id is not None:
            context = context.with_connection(
                context.require_connection()
            )

        if session_capacity is not None and session_capacity < 1:
            raise ValueError(
                "session_capacity must be at least 1"
            )

        configured_capacity = (
            AppManager.connection_session_capacity()
            if session_capacity is None
            else session_capacity
        )

        if (
            AppManager.is_strict()
            and configured_capacity
            > AppManager.connection_session_capacity()
        ):
            raise ValueError(
                "session_capacity exceeds the configured strict "
                "connection limit"
            )

        self._gateway = gateway
        self._context = context
        self._session_capacity = configured_capacity

    @property
    def gateway(self) -> ComGateway:
        return self._gateway

    @property
    def context(self) -> SapContext:
        return self._context

    @property
    def id(self) -> str:
        return self._context.require_connection()

    @property
    def _com(self) -> DispatchLike:
        return self._gateway.get_connection(self.id)

    @property
    def application(self) -> Application:
        from .application import Application

        return Application(
            gateway=self._gateway,
            context=SapContext(
                application_id=self._context.application_id,
            ),
        )

    @property
    def sessions(self) -> tuple[Session, ...]:
        """
        Return a snapshot of currently open sessions.
        """
        from .session import Session

        connection = self._com

        try:
            children = connection.Children
            count = int(children.Count)
        except Exception as e:
            raise SapComError(
                f"Unable to enumerate sessions for connection {self.id!r}"
            ) from e

        result: list[Session] = []

        for index in range(count):
            try:
                dispatch = children(index)
                session_id = str(dispatch.Id)
                sap_type = str(dispatch.Type)
            except Exception as e:
                raise SapComError(
                    f"Unable to inspect session child {index} for "
                    f"connection {self.id!r}"
                ) from e

            if sap_type != "GuiSession":
                raise SapComError(
                    f"Connection child {index} reported SAP type "
                    f"{sap_type!r}; expected 'GuiSession'"
                )

            result.append(
                Session(
                    gateway=self._gateway,
                    context=self._context.with_session(session_id),
                )
            )

        return tuple(result)

    @property
    def session_count(self) -> int:
        connection = self._com

        try:
            return int(connection.Children.Count)
        except Exception as e:
            raise SapComError(
                f"Unable to obtain the session count for "
                f"connection {self.id!r}"
            ) from e

    @property
    def session_capacity(self) -> int:
        return self._session_capacity

    @property
    def has_session_capacity(self) -> bool:
        return self.session_count < self._session_capacity

    @property
    def description(self) -> str:
        return self._read_string("Description")

    @property
    def connection_string(self) -> str:
        return self._read_string("ConnectionString")

    @property
    def disabled_by_server(self) -> bool:
        return bool(self._read("DisabledByServer"))

    @property
    def runtime_name(self) -> str:
        return self._read_string("Name")

    @property
    def runtime_id(self) -> str:
        return self.id

    def assert_session_capacity(
        self,
        *,
        limit: Optional[int] = None,
    ) -> None:
        actual_limit = (
            self._session_capacity
            if limit is None
            else limit
        )

        if actual_limit < 1:
            raise ValueError("limit must be at least 1")

        current = self.session_count

        if current >= actual_limit:
            raise SapGuiError(
                "Cannot create another SAP GUI session because the "
                f"connection session limit has been reached: "
                f"connection={self.id!r}, current={current}, "
                f"limit={actual_limit}"
            )

    def get_session(
        self,
        index: int = 0,
        /,
    ) -> Session:
        sessions = self.sessions

        try:
            return sessions[index]
        except IndexError as e:
            raise IndexError(
                f"SAP GUI session index out of range: index={index}, "
                f"count={len(sessions)}, connection={self.id!r}"
            ) from e

    def find_session(
        self,
        session_id: str,
        /,
    ) -> Session | None:
        self._validate_non_empty_string(
            session_id,
            name="session_id",
        )

        for session in self.sessions:
            if session.id == session_id:
                return session

        return None

    def require_session(
        self,
        session_id: str,
        /,
    ) -> Session:
        session = self.find_session(session_id)

        if session is None:
            raise SapSessionNotFoundError(
                f"No SAP GUI session {session_id!r} was found under "
                f"connection {self.id!r}"
            )

        return session

    def wait_for_session_capacity(
        self,
        *,
        limit: Optional[int] = None,
        timeout: float = 300.0,
        poll_interval: float = 1.0,
    ) -> Self:
        actual_limit = (
            self._session_capacity
            if limit is None
            else limit
        )

        if actual_limit < 1:
            raise ValueError("limit must be at least 1")

        self._validate_timing(
            timeout=timeout,
            poll_interval=poll_interval,
        )

        deadline = time.monotonic() + timeout

        while True:
            current = self.session_count

            if current < actual_limit:
                return self

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "No SAP GUI session capacity became available: "
                    f"connection={self.id!r}, current={current}, "
                    f"limit={actual_limit}, timeout={timeout}"
                )

            self._pump_messages()
            time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))

    def create_session(
        self,
        *,
        source_session: Session | None = None,
        limit: Optional[int] = None,
        timeout: float = 15.0,
        poll_interval: float = 0.1,
    ) -> Session:
        """
        Create and return a new session under this connection.

        SAP exposes ``CreateSession`` on a GuiSession rather than directly on
        GuiConnection. If ``source_session`` is omitted, the first existing
        session is used.

        A set difference of runtime IDs is used rather than assuming that the
        newly created session is always the final collection element.
        """
        self.assert_session_capacity(limit=limit)
        self._validate_timing(
            timeout=timeout,
            poll_interval=poll_interval,
        )

        existing_sessions = self.sessions

        if not existing_sessions:
            raise SapGuiError(
                "Cannot create a new SAP GUI session because the connection "
                f"{self.id!r} has no existing source session"
            )

        if source_session is None:
            actual_source = existing_sessions[0]
        else:
            if source_session.connection_id != self.id:
                raise ValueError(
                    "source_session belongs to a different connection: "
                    f"expected={self.id!r}, "
                    f"received={source_session.connection_id!r}"
                )
            actual_source = source_session

        before_ids = {
            session.id
            for session in existing_sessions
        }

        try:
            actual_source._com.CreateSession()
        except Exception as e:
            raise SapComError(
                f"Unable to create another session under connection "
                f"{self.id!r}"
            ) from e

        deadline = time.monotonic() + timeout

        while True:
            current_sessions = self.sessions

            for session in current_sessions:
                if session.id not in before_ids:
                    return session

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "SAP GUI accepted CreateSession, but no new session "
                    f"appeared within {timeout} seconds for connection "
                    f"{self.id!r}"
                )

            self._pump_messages()
            time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))

    def close_session(
        self,
        session: Session | str | int,
        /,
    ) -> None:
        """
        Close one session.

        Integer values are converted to SAP's short ``ses[n]`` format.
        Session wrappers and string IDs are also accepted.
        """
        from .session import Session

        if isinstance(session, Session):
            if session.connection_id != self.id:
                raise ValueError(
                    "Cannot close a session belonging to another connection"
                )
            session_id = session.id
        elif isinstance(session, int):
            if session < 0:
                raise ValueError(
                    "A session index cannot be negative"
                )
            session_id = f"ses[{session}]"
        elif isinstance(session, str) and session.strip():
            session_id = session
        else:
            raise TypeError(
                "session must be a Session, non-empty string, or "
                "non-negative integer"
            )

        connection = self._com

        try:
            connection.CloseSession(session_id)
        except Exception as e:
            raise SapComError(
                f"Unable to close session {session_id!r} under "
                f"connection {self.id!r}"
            ) from e

    def close(self) -> None:
        """
        Close the connection and every session belonging to it.
        """
        connection = self._com

        try:
            connection.CloseConnection()
        except Exception as e:
            raise SapComError(
                f"Unable to close SAP GUI connection {self.id!r}"
            ) from e

    def _read(self, property_name: str) -> object:
        connection = self._com

        try:
            return getattr(connection, property_name)
        except Exception as e:
            raise SapComError(
                f"Unable to read connection property "
                f"{property_name!r} from {self.id!r}"
            ) from e

    def _read_string(self, property_name: str) -> str:
        value = self._read(property_name)

        if value is None:
            raise SapComError(
                f"Connection {self.id!r} returned None for "
                f"{property_name!r}"
            )

        return str(value)

    @staticmethod
    def _validate_non_empty_string(
        value: str,
        *,
        name: str,
    ) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{name} must be a non-empty string"
            )

    @staticmethod
    def _validate_timing(
        *,
        timeout: float,
        poll_interval: float,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        if poll_interval <= 0:
            raise ValueError(
                "poll_interval must be greater than zero"
            )

    @staticmethod
    def _pump_messages() -> None:
        try:
            pythoncom.PumpWaitingMessages()
        except Exception:
            # Message pumping is opportunistic during polling. The actual COM
            # operation will still expose relevant failures.
            pass

    def __repr__(self) -> str:
        return f"<Connection id={self.id!r}>"