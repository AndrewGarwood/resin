"""
*`@file`* `gui/utils/find_support`
"""
from typing import (Literal, TypeVar, overload, Protocol)

from resin.gui.components.registry import wrap_dispatch
from resin.gui.exceptions import SapComError, SapGuiError
from ..components.component import Component
from ..com.gateway import ComGateway
from ..context import SapContext
from lute import LogMsg

ComponentT = TypeVar("ComponentT", bound=Component)

class FindContext(Protocol):
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

class FindMixin(FindContext):
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
        self,
        component_id: str,
        /,
        *,
        component_cls: None = None,
        _raise: Literal[False]=False,
    ) -> Component | None: ...

    @overload
    def find(
        self,
        component_id: str,
        /,
        *,
        component_cls: type[ComponentT],
        _raise: Literal[False]=False,
    ) -> ComponentT | None: ...

    @overload
    def find(
        self,
        component_id: str,
        /,
        *,
        component_cls: None = None,
        _raise: Literal[True]=True,
    ) -> Component: ...

    @overload
    def find(
        self,
        component_id: str,
        /,
        *,
        component_cls: type[ComponentT],
        _raise: Literal[True]=True,
    ) -> ComponentT: ...
    
    @overload
    def find(
        self,
        component_id: str,
        /,
        *,
        component_cls: None = None,
        _raise: bool,
    ) -> Component | None: ...

    @overload
    def find(
        self,
        component_id: str,
        /,
        *,
        component_cls: type[ComponentT],
        _raise: bool,
    ) -> ComponentT | None: ...

    def find(
        self,
        component_id: str,
        /,
        *,
        component_cls: type[ComponentT] | None = None,
        _raise: bool = False,
    ) -> Component | ComponentT | None:
        try:
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