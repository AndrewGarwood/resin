"""
*`@file`* `resin/gui/components/com_proxy`
"""

import win32com.client as win32
from typing import Optional
from lute import (LogMsg, annotate)

class ComProxy:
    def __init__(
        self, 
        *, 
        app_id: Optional[str] = None, 
        conn_id: Optional[str] = None, 
        session_id: Optional[str] = None,
        _id: Optional[str] = None,
        verbose: bool = False
    ) -> None:
        self._app_id = app_id
        self._conn_id = conn_id
        self._session_id = session_id
        self._id = _id
        self.verbose = verbose
    
    def _com_app(self) -> win32.CDispatch:
        sapgui = win32.GetObject("SAPGUI")
        return sapgui.GetScriptingEngine
    
    def _com_connection(self) -> win32.CDispatch:
        app = self._com_app()
        for i in range(app.Children.Count):
            c = app.Children(i)
            if (c.Id == self._conn_id): return c
        raise RuntimeError(LogMsg(f"Connection not found: {self._conn_id}"))
        
    def _com_session(self) -> win32.CDispatch:
        conn = self._com_connection()
        for i in range(conn.Children.Count):
            s = conn.Children(i)
            if (s.Id == self._session_id): return s
        raise RuntimeError(LogMsg(f"Session not found: {self._session_id}"))

    def _resolve(self) -> win32.CDispatch:
        session = self._com_session()
        obj = session.FindById(self._id)
        if self.verbose:
            print(LogMsg(f"Resolved object: {obj.Id}")) # -> Resolved object: wnd[0]/usr/ctxtDY_PATH
        return obj