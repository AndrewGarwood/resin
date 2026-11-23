"""
*`@file`* `gui/core/session`
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Literal, TypeVar, overload
from win32com.client import CDispatch

from ..com.gateway import ComGateway
from ..com.types import DispatchLike
from ..components.factory import wrap_dispatch
from ..context import SapContext
from ..exceptions import (
    SapComError,
    SapComponentNotFoundError,
    SapGuiError,
    SapGuiStatusError
)
from pyqi import (require, Function, safe)
from lute import LogMsg, annotate
from resin.utils import runtime
from resin.gui.utils import (gui_id as GUI, SupportsSet)
from ..utils.mixin import (FindMixin)

if TYPE_CHECKING:
    from .connection import Connection
    from ..components import Component
    from ..components.window import FrameWindow, MainWindow
    from ..components.status_bar import Statusbar
    from ..components.control import (TextField, CheckBox)
    from ..com.gateway import ComGateway


ComponentT = TypeVar("ComponentT", bound="Component")


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
    def active_window(self) -> FrameWindow:
        try:
            dispatch = self.gateway.get_property(
                self._com, 
                "ActiveWindow", 
                _raise=True, 
                source=f"Session.active_window"
            )
            return wrap_dispatch(
                dispatch,
                gateway=self._gateway,
                context=self._context
            )
        except SapComError as e:
            raise SapComError(LogMsg.err(
                e,
                "Failed to read ActiveWindow property of self._com",
                session_id = safe.readattr(self, "id", use_repr=True)
            )) from e
        except Exception as e:
            raise SapComError(
                f"Unable to obtain the active window for session "
                f"{self.id!r}"
            ) from e

    @property
    def main_window(self) -> MainWindow:
        """ - returns window at index `0` """
        try:
            from ..components.window import MainWindow
            return self.find(
                GUI.wnd(GUI.MAIN_WINDOW_INDEX), 
                component_cls=MainWindow, 
                _raise=True
            )
        except SapGuiError:
            raise
        except Exception as e:
            raise SapGuiError(LogMsg.err(
                e, 
                f"Failed to get MainWindow of session"
            )) from e

    @property
    def info(self) -> CDispatch:
        """
        Return the raw GuiSessionInfo COM object.

        GuiSessionInfo does not consistently behave like a session component,
        so it should not be forced through Component.FindById resolution.
        A dedicated immutable SessionInfo value object can be added later.
        """
        return self.gateway.get_property(
            self._com, 
            "Info", 
            _raise=True, 
            source="Session.info(self)"
        )

    @property
    def transaction(self) -> str:
        try:
            return str(self.info.Transaction)
        except Exception as e:
            raise SapComError(
                f"Unable to read the transaction for session {self.id!r}"
            ) from e

    # @property
    # def okcd(self):
    #     return self.find("wnd[0]/tbar[0]/okcd", _raise=True)

    # @property
    # def user_area(self):
    #     return self.find("wnd[0]/usr", _raise=True)

    # @property
    # def usr(self):
    #     return self.user_area

    # @property
    # def statusbar(self) -> Any:
    #     return self.find("wnd[0]/sbar", _raise=True)
    @property
    def statusbar(self) -> Statusbar:
        from ..components.status_bar import Statusbar
        return self.find(
            GUI.sbar(0),
            component_cls=Statusbar, 
            _raise=True
        )

    @property
    def status(self) -> str:
        try:
            return self.statusbar.status
        except Exception as e:
            raise SapComError(LogMsg.err(
                e,
                f"Failed to read the status bar for session",
                session_id=repr(self.id)
            )) from e

    def get_status(self) -> str:
        """ *`@returns`* `safe.readattr(self, "status")` """
        return safe.to_str(safe.readattr(self, "status"))

    def press_button(
        self,
        btn_id: str,
        /,
        *,
        timeout: float=5.0
    ):
        """ throws error if button not found or other error """
        from ..components.control import Button
        try:
            self.wait_for_component(
                btn_id,
                component_cls=Button, 
                _raise=True,
                timeout=timeout
            ).press()
        except Exception as e:
            raise SapGuiError(LogMsg.err(
                e, 
                f"Failed to find and press button",
                btn_id=btn_id
            )) from e

    def set_field_value(
        self, 
        field_id: str, 
        value: Any, # TODO handle when value is list[any]
        /, 
        field_cls: type[TextField] | type[CheckBox],
        timeout: float=5.0
    ):
        try:
            self.wait_for_component(
                field_id, 
                component_cls=field_cls, 
                _raise=True, 
                timeout=timeout
            ).set(value)
        except Exception as e:
            raise SapGuiError(LogMsg.err(
                e,
                f"Failed to set field value",
                field_id=field_id,
                field_cls=field_cls.__name__,
                value=annotate(value)
            )) from e

    def select_radio_option(
        self, 
        btn_id: str, 
        /, 
        option: str | None=None,
        timeout: float=5.0
    ):
        """
        *`@param`* `option (str | None)` must be provided when `btn_id` does not contain the option itself
        - i.e. `if` `btn_id` = `'wnd[i]/path/to/btn/rad'` then must provide option
        - but `if` `btn_id` = `'wnd[i]/path/to/btn/rad{option}'` then option will be taken from `btn_id`
        - TODO: maybe handle this in `models/_field/_resolve`
        """
        from ..components.control import RadioButton
        try:
            btn_id = require.non_empty_string(btn_id, "Radio Button Id")
            id_parts = require.non_empty_string(btn_id, "Radio Button Id").rsplit("/", 1)
            if (not id_parts):
                raise ValueError(f"Invalid btn_id")
            stem = id_parts[-1]
            lower_stem = stem.lower()
            if (not option):
                if (lower_stem.endswith("rad")):
                    raise ValueError(LogMsg(
                        "Must provide argument 'option (str)' when btn_id is base component id" #  ('wnd[i]/base/component/rad')
                    ))
                if (len(lower_stem) > 3 and lower_stem.startswith("rad")):
                    option = stem[3:]
            if (not option):
                raise ValueError(
                    f"Unable to determine radio button option"
                )
            resolved_id = GUI.join(id_parts[0], f"rad{option}")
            self.wait_for_component(
                resolved_id, 
                component_cls=RadioButton, 
                _raise=True, 
                timeout=timeout
            ).select()
            return None
        except SapGuiError:
            raise
        except Exception as e:
            raise SapGuiError(LogMsg.err(
                e,
                f"Failed to select radio button option",
                btn_id=btn_id,
                option=option
            )) from e

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
            result = self._com.GetVKeyDescription(
                require.non_negative_integer(key, "vkey")
            )
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
        timeout, poll_interval = runtime.validate_polling(timeout, poll_interval)

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

    @overload
    def wait_for_component(
        self, 
        component_id: str, 
        /, 
        *, 
        component_cls: None=None,
        _raise: Literal[True]=True, 
        timeout: float=5.0, 
        poll_interval: float=0.1
    ) -> Component: ...

    @overload
    def wait_for_component(
        self, 
        component_id: str, 
        /, 
        *, 
        component_cls: type[ComponentT],
        _raise: Literal[True]=True, 
        timeout: float=5.0, 
        poll_interval: float=0.1
    ) -> ComponentT: ...

    @overload
    def wait_for_component(
        self, 
        component_id: str, 
        /, 
        *, 
        component_cls: type[ComponentT],
        _raise: Literal[False]=False, 
        timeout: float=5.0, 
        poll_interval: float=0.1
    ) -> ComponentT | None: ...

    @overload
    def wait_for_component(
        self, 
        component_id: str, 
        /, 
        *, 
        component_cls: None=None,
        _raise: Literal[False]=False, 
        timeout: float=5.0, 
        poll_interval: float=0.1
    ) -> Component | None: ...

    def wait_for_component(
        self, 
        component_id: str, 
        /, 
        *, 
        component_cls: type[ComponentT] | None=None,
        _raise: bool=False, 
        timeout: float=5.0, 
        poll_interval: float=0.1
    ) -> Any:
        """ 
        *`@returns`* `Function.Deferred(self.find, component_id, _raise=_raise, component_cls=component_cls)` 
        if component is found within deadline 
        """
        return runtime.poll_until(
            Function.Deferred(
                self.find, 
                component_id, 
                _raise=_raise, 
                component_cls=component_cls
            ), 
            timeout=timeout, 
            poll_interval=poll_interval, 
            description=f"session.find({component_id})",
            _raise=_raise
        )

__all__ = ["Session"]