"""
*`@file`* `resin/gui/components/component`

- [SAP GuiComponent](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/8ba9356d3c524ee2b3ded3f97b0a86ba.html).
"""
from __future__ import annotations
import win32com.client as win32
from typing import Any, Optional
from lute import (LogMsg)
from ._proxy import (ComProxy)
from ._collection import Collection


class Component(ComProxy):
    """
    *`@extends`* `ComProxy`
    """
    def __init__(
        self, 
        *, 
        conn_id: Optional[str] = None, 
        session_id: Optional[str] = None, 
        _id: Optional[str] = None
    ):
        super().__init__(conn_id=conn_id, session_id=session_id, _id=_id)

    @property
    def _com(self) -> win32.CDispatch:
        """ = `self._resolve()` = `ComProxy._com_session().FindById(self._id)` """
        return self._resolve()

    @property
    def id(self) -> str:
        if not isinstance(self._id, str):
            raise RuntimeError(LogMsg(f"[Component.id] self._id is not a string"))
        return self._id

    @property
    def name(self) -> str:
        return str(self._com.Name)

    @property
    def type(self) -> str:
        return str(self._com.Type)

    @property
    def type_as_number(self) -> int:
        return self._com.TypeAsNumber
    
    @property 
    def container_type(self) -> bool:
        return self._com.ContainerType

    @property
    def parent(self) -> Component:
        # TODO: maybe remove this and only use com_parent where necessary
        p = self._com.Parent
        if not isinstance(p, win32.CDispatch):
            raise RuntimeError(
                f"[Component.parent] parent is not CDispatch {type(p)=}"
            )
        
        return Component(
            conn_id=self._conn_id,
            session_id=self._session_id,
            _id=p.Id
        )

    @property
    def com_parent(self) -> win32.CDispatch:
        """ *`@returns`* `self._com.Parent` """
        p = self._com.Parent
        if not isinstance(p, win32.CDispatch):
            raise RuntimeError(
                f"[Component.com_parent] parent is not CDispatch {type(p)=}"
            )
        return p

    def __repr__(self):
        cls_name = self.__class__.__name__
        try:
            return f"<{cls_name} id={self.id}>"
        except Exception:
            return f"<{cls_name}>"


class VComponent(Component):
    """
    Python analogue of [SAP GuiVComponent](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/26824bb464b045558bf5c71a617aa7fb.html).

    "The GuiVComponent interface is exposed by all visual objects, such as windows, buttons or text fields."
    """

    @property
    def text(self) -> str:
        return str(self._com.Text)

    @property
    def changeable(self) -> bool:
        """ 'An object is changeable if it is neither disabled nor read-only.' """
        return bool(self._com.Changeable)

    @property
    def enabled(self) -> bool:
        try:
            return bool(self._com.Enabled)
        except Exception as e:
            return True

    def dump_state(self, inner_obj: str="") -> Any: # Collection
        return self._com.DumpState(inner_obj)
    
    def set_focus(self):
        self._com.SetFocus()
        return self

    
    def visualize(self, on: bool, inner_obj: str=""):
        """_summary_

        Args:
            on (bool):
                - True: will display a red frame around the specified component
                - False: remove red frame
            inner_obj (str, optional): _description_. Defaults to "".

        Returns:
            _type_: _description_
        """
        return self._com.Visualize(on, inner_obj)


class ComponentCollection(Collection[Component]):
    """ `Collection<Component>` """
    ...

