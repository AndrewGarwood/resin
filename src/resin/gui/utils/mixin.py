"""
*`@file`* `gui/utils/mixin`
"""
from __future__ import annotations
from typing import (Literal, TypeVar, overload, Protocol, TYPE_CHECKING)
from resin.gui.components.factory import wrap_dispatch
from resin.gui.exceptions import SapComError, SapGuiError
from ..com.gateway import ComGateway
from ..context import SapContext
from lute import LogMsg

if TYPE_CHECKING:
    from resin.gui.components.component import Component

T = TypeVar('T')
ComponentT = TypeVar("ComponentT", bound="Component")

class SupportsFind(Protocol):
    """
    *`@protocol`* 
    ```
    - @property def context(self) -> SapContext: ...
    - @property def gateway(self) -> ComGateway: ...
    - @property def session_id(self) -> str: ...
    - @property def connection_id(self) -> str: ...
    ```
    """
    @property
    def context(self) -> SapContext: ...
    @property
    def gateway(self) -> ComGateway: ...
    @property
    def session_id(self) -> str: ...
    @property
    def connection_id(self) -> str: ...

class FindMixin():
    """
    *`@extends`* `FindContext(Protocol)` → classes that inherit `FindMixin` *must* also implement:
    ```
    - @property def context(self) -> SapContext: ...
    - @property def gateway(self) -> ComGateway: ...
    - @property def session_id(self) -> str: ...
    - @property def connection_id(self) -> str: ...
    ```
    """
    
    @overload
    def find(
        self: SupportsFind,
        component_id: str,
        /,
        *,
        component_cls: None = None,
        _raise: Literal[False] = False,
    ) -> Component | None: ...

    @overload
    def find(
        self: SupportsFind,
        component_id: str,
        /,
        *,
        component_cls: None = None,
        _raise: Literal[True],
    ) -> Component: ...


    @overload
    def find(
        self: SupportsFind,
        component_id: str,
        /,
        *,
        component_cls: type[ComponentT],
        _raise: Literal[False] = False,
    ) -> ComponentT | None: ...

    @overload
    def find(
        self: SupportsFind,
        component_id: str,
        /,
        *,
        component_cls: type[ComponentT],
        _raise: Literal[True],
    ) -> ComponentT: ...
    
    @overload
    def find(
        self: SupportsFind,
        component_id: str,
        /,
        *,
        component_cls: type[ComponentT] | None = None,
        _raise: bool,
    ) -> Component | ComponentT | None: ...

    def find(
        self: SupportsFind,
        component_id: str,
        /,
        *,
        component_cls: type[ComponentT] | None = None,
        _raise: bool = False,
    ) -> Component | ComponentT | None:
        
        try:
            if (component_cls is not None):
                from resin.gui.components.component import Component
                if (not issubclass(component_cls, Component)):
                    raise TypeError(LogMsg.bad_arg(
                        component_cls, "component_cls", 
                        "component_cls must extend Component", 
                        Component, "class <name>(Component)"
                    ))
            obj = self.gateway.find_component(
                self.connection_id,
                self.session_id,
                component_id,
                raise_on_missing=_raise,
            )

            if obj is None: return None
            if component_cls is None:
                return wrap_dispatch(
                    obj,
                    gateway=self.gateway,
                    context=self.context,
                )
            return component_cls(
                gateway=self.gateway,
                context=self.context.with_component(str(obj.Id))
            )
        except SapGuiError:
            raise
        except Exception as e:
            raise SapComError(
                LogMsg.err(
                    e,
                    component_id=component_id,
                    component_cls=str(component_cls),
                    _raise=_raise,
                )
            ) from e
