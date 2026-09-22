"""
*`@file`* `resin/gui/core/_session`
- [GuiSession](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/a4e022f6c155414d9c8ae8eba422cac5.html)
- [GuiSessionInfo](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/15fb37a11e9143eb8eb0e5da85958422.html)

"""
from __future__ import annotations
from typing import (Any, Generic, TypeVar)
import win32com.client as win32
from abc import (ABC, abstractmethod)

from ..components.component import Component
from ..components.container import BaseContainer
import lute
LogMsg = lute.LogMsg


class BaseSession(BaseContainer[Component], ABC):
    """ *`@extends`* `BaseContainer[Component]` """
    def __init__(self, conn_id: str, session_id: str):
        if not isinstance(conn_id, str):
            raise ValueError(LogMsg.bad_arg(
                conn_id, "conn_id", "Invalid connection id for Session", str
            ))
        if not isinstance(session_id, str):
            raise ValueError(LogMsg.bad_arg(
                conn_id, "conn_id", "Invalid session id for Session", str
            ))
        super().__init__(
            conn_id=conn_id, 
            session_id=session_id, 
            _id=None
        )
    
    @property
    def _com(self) -> win32.CDispatch:
        return self._com_session()
    
    @property
    def id(self) -> str:
        if not isinstance(self._session_id, str):
            raise RuntimeError(f"[Session.id] self._session_id is not a string!")
        return self._session_id

    @property
    def is_active(self) -> bool:
        """
        `Public Property IsActive As Byte`
        - `TRUE` if the session window is active.
        - `FALSE` overwise.
        """
        return bool(self._com.IsActive)
    
    @property
    def busy(self):
        """
        `Public Property Busy As Byte`
        - **While SAP GUI is waiting for data from the server, any Scripting call 
        will not return, which blocks the executing thread.**
        - A way to prevent this is to check the busy property of the
        session. **If this property is True, then a subsequent Scripting
        call will wait for the server communication to be finished.**
        """
        return bool(self._com.Busy)
    
    @property
    def passport_transaction_id(self):
        """
        `Public Property PassportTransactionId As String`
        The unique ID of the transaction. Part of the passport information.
        """
        return self._com.PassportTransactionId

    @property
    @abstractmethod
    def parent(self) -> Any: ...

    
    @property
    @abstractmethod
    def okcd(self) -> Any: ...

    
    @property
    @abstractmethod
    def usr(self) -> Any: ...

    
    @property
    @abstractmethod
    def statusbar(self) -> Any: ...

    @property
    @abstractmethod
    def status(self) -> Any: ... # self.statusbar.status

    
    @abstractmethod
    def total_session_count(self) -> int: ...

class SessionInfo(Component):
    """
    """
    __slots__ = ()
    @property
    def transaction(self) -> str:
        """ 
        `(Read-only)` - `Public Property Transaction As String` 
        - The transaction that is currently being executed.
        """
        return self._com.Transaction
    
    @property
    def response_time(self) -> int:
        """
        `(Read-only)` - `Public Property ResponseTime As Long`
        - This is the time that is spent on network communication
        from the moment data are sent to the server to the moment
        the server response arrives. The **unit is milliseconds.**
        """
        return self._com.ResponseTime
    
    @property
    def system_session_id(self) -> str:
        """
        `(Read-only)` - `Public Property SystemSessionId As String`
        - All SAP GUI sessions of the same connection are represented on the 
        server with the same SystemSessionId. Using
        SystemSessionId and SessionNumber, it is possible to find a
        matching SAP GUI session from an ABAP application.
        """
        return self._com.SystemSessionId
    @property
    def user(self) -> str:
        """ 
        `(Read-only)` - `Public Property User As String` 
        - The SAP name of the user logged into the system
        """
        return self._com.User
    @property
    def system_name(self) -> str:
        """ 
        `(Read-only)` - `Public Property SystemName As String` 
        - This is the name of the SAP system.
        """
        return self._com.SystemName
    @property
    def system_number(self) -> int:
        """ 
        `(Read-only)` - `Public Property SystemNumber As Long`
        - The system number is set only if the session belongs to a connection 
        that was started without load balancing, by specifying an application server.
        """
        return self._com.SystemNumber

    @property
    def application_server(self) -> str:
        """ 
        `(Read-only)` - `Public Property ApplicationServer As String` 
        - The name of the application server is set only if the session
        belongs to a connection that was started without load balancing, 
        by specifying an application server. 
        """
        return self._com.ApplicationServer
    @property
    def client(self) -> str:
        """ 
        `(Read-only)` - `Public Property Client As String`
        - The client selected on the login screen. 
        """
        return self._com.Client
    @property
    def screen_number(self) -> int:
        """ 
        `(Read-only)` - `Public Property ScreenNumber As Long`
        - The number of the screen currently displayed. 
        """
        return self._com.ScreenNumber
    @property
    def session_number(self) -> int:
        """ 
        `(Read-only)` - `Public Property SessionNumber As Long`
        - The number of the session is also displayed in SAP GUI on the status bar.
        """
        return self._com.SessionNumber