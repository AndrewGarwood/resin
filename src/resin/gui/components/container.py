"""
*`@file`* `resin/gui/components/container`

- [SAP GuiContainer](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/197bc09d272646a097a9a2fff0bb03e7.html).

"""
from __future__ import annotations
from abc import ABC
import win32com.client as win32
from typing import (Type, TypeVar, Optional, Any, Generic, overload, Literal)
from lute import (LogMsg, annotate)
from .component import (Component, VComponent)
from ..utils.concurrency import (busy_safe)
from ..utils.debug import (debug_component)

U = TypeVar('U')
T = TypeVar('T', bound=Component)
# TODO maybe add type for parent component ? e.g. parent of connection is application
# parent of session is connection....

class BaseContainer(ABC, Component, Generic[U]):
    """
    *`@extends`* `Component(ComProxy)`
    
    Adds wrappers for:
    - `Children` 
    - `FindById`
    """
    @property
    def children(self) -> list[win32.CDispatch]:
        """ `_com.Children` """
        arr: list[win32.CDispatch] = []
        _com = self._com
        for i in range(_com.Children.Count):
            c = _com.Children(i)
            if not isinstance(c, win32.CDispatch):
                raise RuntimeError(LogMsg(
                    f"child @ self._com.Children({i=}) is not CDispatch",
                    child=annotate(c),
                    self_com=annotate(_com)
                ))
            arr.append(c)
        return arr

    @property
    def _com(self) -> win32.CDispatch:
        """ `Container._com = self._resolve()` """
        return self._resolve()

    @overload
    def find(self, _id: str, /) -> Optional[Any]: ...

    @overload
    def find(self, _id: str, / cls: Type[T]) -> Optional[T]: ...

    @overload
    def find(self, _id: str, /, cls: Type[T], _raise: Literal[True]=True) -> T: ...

    @busy_safe()
    def find(self, _id: str, / cls: Optional[Type[T]]=None, _raise: bool=False):
        _com: Optional[win32.CDispatch] = None
        try:
            _com = self._com
            obj = _com.FindById(_id, False) # _raise
            if (not obj):
                if (_raise):
                    raise RuntimeError("FindById returned None")
                return None
            if (cls is None):
                return Component(
                    _id=obj.Id, 
                    session_id=self._session_id, 
                    conn_id=self._conn_id
                )
            if (cls.__name__ == "Connection"):
                return cls(conn_id=obj.Id)
            return cls(
                _id=obj.Id, 
                session_id=self._session_id, 
                conn_id=self._conn_id
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e,
                f"Unable to find child component with id={_id}",
                self=debug_component(_com) if (_com) else annotate(self),
                cls=annotate(cls),
                _raise=_raise
            ))


class BaseVContainer(VComponent, BaseContainer[U]):
    """
    ***@not_implemented*** - methods will raise `NotImplementedError()`
    
    [SAP GuiVContainer](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/76a8c4e46d1d4f8caa5f70b6dcfc5f34.html)
    """
    def find_all_by_name(self, name: str, /, _type: str) -> list[U]:
        """ `self._com.FindAllByName(name, _type)` """
        raise NotImplementedError()
    def find_all_by_name_ex(self, name: str, /, _type_as_number: int) -> list[U]:
        """ `self._com.FindAllByNameEx(name, _type_as_number)` """
        raise NotImplementedError()