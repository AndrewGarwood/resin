from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, TypeVar, overload

import pythoncom
from win32com.client import CDispatch
from ..com.gateway import ComGateway
from ..com.types import DispatchLike
from ..components.component import Component
from ..components.registry import wrap_dispatch
from ..context import SapContext
from ..exceptions import (
    SapComponentNotFoundError,
    SapComError,
    SapGuiStatusError
)
from ..utils.types import (require_non_empty_string, require_positive_number)

if TYPE_CHECKING:
    from ..components.container import Container
    from .connection import Connection


ComponentT = TypeVar("ComponentT", bound=Component)


class Session:
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
        return self._context.require_session()[0]

    @property
    def id(self) -> str:
        return self._context.require_session()[1]

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
        return bool(self._read("Busy"))

    @property
    def is_active(self) -> bool:
        return bool(self._read("IsActive"))

    @property
    def passport_transaction_id(self) -> str:
        value = self._read("PassportTransactionId")
        return "" if value is None else str(value)

    @property
    def active_window(self) -> Component:
        session = self._com

        try:
            dispatch = session.ActiveWindow
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
        return self._read("Info")

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
    #     return self.find("wnd[0]/tbar[0]/okcd", raise_on_missing=True)

    # @property
    # def user_area(self) -> Component:
    #     return self.find_or_raise("wnd[0]/usr")

    # @property
    # def usr(self) -> Component:
    #     return self.user_area

    # @property
    # def statusbar(self) -> Component:
    #     return self.find_or_raise("wnd[0]/sbar")

    # @property
    # def status(self) -> str:
    #     statusbar = self.statusbar

    #     try:
    #         return str(statusbar._com.Text)
    #     except Exception as e:
    #         raise SapComError(
    #             f"Unable to read the status bar for session {self.id!r}"
    #         ) from e

    def find(
        self,
        component_id: str,
        /,
        *,
        raise_on_missing: bool = True,
    ) -> Component | None:
        """
        Find and dynamically wrap a component in this session.
        """
        require_non_empty_string(component_id, 'component_id')
        dispatch = self._gateway.find_component(
            self.connection_id,
            self.id,
            component_id,
            raise_on_missing=raise_on_missing,
        )

        if dispatch is None:
            return None

        return wrap_dispatch(
            dispatch,
            gateway=self._gateway,
            context=self._context,
        )

    def exists(
        self,
        component_id: str,
        /,
    ) -> bool:
        self._validate_component_id(component_id)

        return self._gateway.component_exists(
            self.connection_id,
            self.id,
            component_id,
        )

    def wait_for_idle(
        self,
        *,
        timeout: float = 60.0,
        poll_interval: float = 0.05,
    ) -> Session:
        self._validate_timing(
            timeout=timeout,
            poll_interval=poll_interval,
        )

        deadline = time.monotonic() + timeout

        while True:
            if not self.busy:
                return self

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"SAP GUI session remained busy for more than "
                    f"{timeout} seconds: connection={self.connection_id!r}, "
                    f"session={self.id!r}"
                )

            self._pump_messages()
            time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))

    # def wait_for_component( # move out of class
    #     self,
    #     component_id: str,
    #     /,
    #     *,
    #     timeout: float = 5.0,
    #     poll_interval: float = 0.1,
    # ) -> Component:
    #     self._validate_component_id(component_id)
    #     self._validate_timing(
    #         timeout=timeout,
    #         poll_interval=poll_interval,
    #     )

    #     deadline = time.monotonic() + timeout
    #     last_error: Exception | None = None

    #     while True:
    #         try:
    #             component = self.find(component_id, raise_on_missing=False)

    #             if component is not None:
    #                 return component
    #         except SapComError as e:
    #             last_error = e

    #         if time.monotonic() >= deadline:
    #             message = (
    #                 f"SAP GUI component {component_id!r} did not appear "
    #                 f"within {timeout} seconds in session {self.id!r}"
    #             )

    #             if last_error is not None:
    #                 raise TimeoutError(message) from last_error

    #             raise TimeoutError(message)

    #         self._pump_messages()
    #         time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))

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
        self._validate_non_empty_string(
            command,
            name="command",
        )

        session = self._com

        try:
            session.SendCommand(command)
        except Exception as e:
            raise SapComError(
                f"Unable to send SAP command {command!r} to session "
                f"{self.id!r}"
            ) from e

        return self

    def start_transaction(
        self,
        transaction_code: str,
        /,
    ) -> Session:
        self._validate_non_empty_string(
            transaction_code,
            name="transaction_code",
        )

        session = self._com

        try:
            session.StartTransaction(transaction_code)
        except Exception as e:
            raise SapComError(
                f"Unable to start SAP transaction "
                f"{transaction_code!r} in session {self.id!r}"
            ) from e

        return self

    def end_transaction(self) -> Session:
        session = self._com

        try:
            session.EndTransaction()
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
                f"session {self.id!r}"
            ) from e

        return str(result)

    def get_vkey_description(
        self,
        key: int,
        /,
    ) -> str:
        if not isinstance(key, int):
            raise TypeError("key must be an integer")

        if key < 0:
            raise ValueError("key cannot be negative")

        session = self._com

        try:
            result = session.GetVKeyDescription(key)
        except Exception as e:
            raise SapComError(
                f"Unable to obtain the description for SAP virtual key "
                f"{key}"
            ) from e

        return str(result)

    # def raise_on_error(self) -> None:
    #     """
    #     Raise when the current status bar reports an SAP error message.
    #     """
    #     statusbar = self.statusbar
    #     dispatch = statusbar._com

    #     try:
    #         message_type = str(dispatch.MessageType)
    #         message_id = str(dispatch.MessageId)
    #         message_number = str(dispatch.MessageNumber)
    #         text = str(dispatch.Text)
    #     except Exception as e:
    #         raise SapComError(
    #             f"Unable to inspect the status bar for session {self.id!r}"
    #         ) from e

    #     if message_type == "E":
    #         raise SapGuiStatusError(
    #             text=text,
    #             message_id=message_id,
    #             message_number=message_number,
    #             session_id=self.id,
    #         )

    def close(self) -> None:
        self.connection.close_session(self)

    def _read(self, property_name: str) -> Any:
        session = self._com

        try:
            return getattr(session, property_name)
        except Exception as e:
            raise SapComError(
                f"Unable to read session property {property_name!r} "
                f"from {self.id!r}"
            ) from e

    @staticmethod
    def _validate_component_id(component_id: str) -> None:
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError(
                "component_id must be a non-empty string"
            )

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
            pass

    def __repr__(self) -> str:
        return (
            f"<Session connection_id={self.connection_id!r} "
            f"id={self.id!r}>"
        )

from dataclasses import dataclass


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