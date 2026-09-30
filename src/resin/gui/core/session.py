"""
*`@file`* `gui/core/session`
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, TypeVar
from dataclasses import dataclass
from win32com.client import CDispatch

from resin.gui.com.runtime import validate_polling
from ..com.gateway import ComGateway
from ..com.types import DispatchLike
from ..components.component import Component
from ..components.registry import wrap_dispatch
from ..context import SapContext
from ..exceptions import (
    SapComError,
    SapGuiStatusError
)
from pyqi import require
from resin.gui.com import runtime
from ..utils.mixin import (FindMixin)

if TYPE_CHECKING:
    from .connection import Connection


ComponentT = TypeVar("ComponentT", bound=Component)


class Session(FindMixin):
    """
    Wrapper around one SAP GUI session.

    A session is identified by a connection ID and session ID. The COM
    dispatch object is resolved on each operation through ``ComGateway``.
    """

    def __init__(
        self,
        /,
        gateway: ComGateway,
        context: SapContext,
    ) -> None:
        context.require_session()
        if context.component_id is not None:
            context = SapContext(
                application_id=context.application_id,
                connection_id=context.connection_id,
                session_id=context.session_id,
            )
        self._gateway = gateway
        self._context = context

    @property
    def gateway(self) -> ComGateway:
        return self._gateway

    @property
    def context(self) -> SapContext:
        return self._context

    @property
    def connection_id(self) -> str:
        return self._context.get_connection_id()

    @property
    def id(self) -> str:
        return self._context.get_session_id()

    @property
    def session_id(self) -> str:
        """ superfluous, but used to satisfy Protocol from FindMixin """
        return self.id

    @property
    def _com(self) -> DispatchLike:
        return self._gateway.get_session(
            self.connection_id,
            self.id,
        )

    @property
    def connection(self) -> Connection:
        from .connection import Connection

        return Connection(
            gateway=self._gateway,
            context=SapContext(
                application_id=self._context.application_id,
                connection_id=self.connection_id,
            ),
        )

    @property
    def parent(self) -> Connection:
        return self.connection

    @property
    def busy(self) -> bool:
        return self._gateway.get_property(self._com, "Busy", bool, _raise=True)

    @property
    def is_active(self) -> bool:
        return self._gateway.get_property(self._com, "IsActive", bool, _raise=True)

    @property
    def passport_transaction_id(self) -> str:
        return self._gateway.get_property(
            self._com, 
            "PassportTransactionId", 
            str, 
            default=""
        )

    @property
    def active_window(self) -> Component:
        try:
            dispatch = self._com.ActiveWindow
        except Exception as e:
            raise SapComError(
                f"Unable to obtain the active window for session "
                f"{self.id!r}"
            ) from e

        return wrap_dispatch(
            dispatch,
            gateway=self._gateway,
            context=self._context,
        )

    @property
    def info(self) -> CDispatch:
        """
        Return the raw GuiSessionInfo COM object.

        GuiSessionInfo does not consistently behave like a session component,
        so it should not be forced through Component.FindById resolution.
        A dedicated immutable SessionInfo value object can be added later.
        """
        return self.gateway.get_property(self._com, "Info", _raise=True, source="Session.info(self)")

    @property
    def transaction(self) -> str:
        try:
            return str(self.info.Transaction)
        except Exception as e:
            raise SapComError(
                f"Unable to read the transaction for session {self.id!r}"
            ) from e

    # @property
    # def okcd(self) -> Component:
    #     return self.find("wnd[0]/tbar[0]/okcd", _raise=True)

    # @property
    # def user_area(self) -> Component:
    #     return self.find("wnd[0]/usr", _raise=True)

    # @property
    # def usr(self) -> Component:
    #     return self.user_area

    @property
    def statusbar(self) -> Component:
        return self.find("wnd[0]/sbar", _raise=True)

    @property
    def status(self) -> str:
        statusbar = self.statusbar
        try:
            return str(statusbar._com.Text)
        except Exception as e:
            raise SapComError(
                f"Unable to read the status bar for session {self.id!r}"
            ) from e

    def exists(
        self,
        component_id: str,
        /,
    ) -> bool:
        return self._gateway.component_exists(
            self.connection_id,
            self.id,
            require.non_empty_string(component_id),
        )

    def create_session(
        self,
        *,
        limit: int | None = None,
        timeout: float = 15.0,
        poll_interval: float = 0.1,
    ) -> Session:
        """
        Create and return another session under the same connection.
        """
        return self.connection.create_session(
            source_session=self,
            limit=limit,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    def send_command(
        self,
        command: str,
        /,
    ) -> Session:
        try:
            self._com.SendCommand(require.non_empty_string(
                command,
                name="command",
            ))
        except Exception as e:
            raise SapComError(
                f"Unable to send SAP command {command!r} to session "
                f"{self.id!r}"
            ) from e

        return self

    def start_transaction(
        self,
        code: str,
        /,
    ) -> Session:
        try:
            self._com.StartTransaction(require.non_empty_string(
                code,
                name="transaction_code",
            ))
        except Exception as e:
            raise SapComError(
                f"Unable to start SAP transaction "
                f"{code!r} in session {self.id!r}"
            ) from e

        return self

    def end_transaction(self) -> Session:
        try:
            self._com.EndTransaction()
        except Exception as e:
            raise SapComError(
                f"Unable to end the transaction in session {self.id!r}"
            ) from e
        return self

    def get_object_tree(
        self,
        component_id: str = "",
        /,
        *,
        properties: object | None = None,
    ) -> str:
        if not isinstance(component_id, str):
            raise TypeError("component_id must be a string")
        session = self._com
        try:
            if properties is None:
                result = session.GetObjectTree(component_id)
            else:
                result = session.GetObjectTree(
                    component_id,
                    properties,
                )
        except Exception as e:
            raise SapComError(
                f"Unable to obtain the SAP GUI object tree for "
                f"session {ComGateway.get_property(session, 'Id')!r}"
            ) from e
        return str(result)

    def get_vkey_description(
        self,
        key: int,
        /,
    ) -> str:
        try:
            result = self._com.GetVKeyDescription(require.positive_integer(key, "vkey"))
        except Exception as e:
            raise SapComError(
                f"Unable to obtain the description for SAP virtual key "
                f"{key}"
            ) from e
        return str(result)

    def raise_on_error(self) -> None:
        """
        Raise when the current status bar reports an SAP error message.
        """
        statusbar = self.statusbar
        dispatch = statusbar._com

        try:
            message_type = str(dispatch.MessageType)
            message_id = str(dispatch.MessageId)
            message_number = str(dispatch.MessageNumber)
            text = str(dispatch.Text)
        except Exception as e:
            raise SapComError(
                f"Unable to inspect the status bar for session {self.id!r}"
            ) from e

        if message_type == "E":
            raise SapGuiStatusError(
                text=text,
                message_id=message_id,
                message_number=message_number,
                session_id=self.id,
            )

    def close(self) -> None:
        self.connection.close_session(self)

    def __repr__(self) -> str:
        return (
            f"<Session connection_id={self.connection_id!r} "
            f"id={self.id!r}>"
        )

    @staticmethod
    def wait_for_idle(
        session: Session,
        /,
        *,
        timeout: float = 60.0,
        poll_interval: float = 0.05,
    ) -> Session:
        timeout, poll_interval = validate_polling(timeout, poll_interval)

        deadline = time.monotonic() + timeout
        while True:
            if (not session.busy):
                return session
            if (time.monotonic() >= deadline):
                raise TimeoutError(
                    f"SAP GUI session remained busy for more than "
                    f"{timeout} seconds: connection={session.connection_id!r}, "
                    f"session={session.id!r}"
                )
            runtime.pump_waiting_messages()
            time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))
        

@dataclass(frozen=True, slots=True)
class SessionInfo:
    transaction: str
    response_time_ms: int
    system_session_id: str
    user: str
    system_name: str
    system_number: int
    application_server: str
    client: str
    screen_number: int
    session_number: int
    
