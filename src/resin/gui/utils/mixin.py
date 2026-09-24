"""
*`@file`* `gui/utils/find_support`
"""
from typing import (Any, Callable, Literal, Optional, TypeVar, overload, Protocol, ClassVar)

from resin.gui.com.types import DispatchLike
from resin.gui.components.registry import wrap_dispatch
from resin.gui.exceptions import SapComError, SapGuiError
from ..components.component import Component
from ..com.gateway import ComGateway
from ..context import SapContext
from lute import LogMsg, annotate

T = TypeVar('T')
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
    
    # @overload
    # def find(
    #     self,
    #     component_id: str,
    #     /,
    #     *,
    #     component_cls: None = None,
    #     _raise: Literal[False]=False,
    # ) -> Component | None: ...

    # @overload
    # def find(
    #     self,
    #     component_id: str,
    #     /,
    #     *,
    #     component_cls: type[ComponentT],
    #     _raise: Literal[False]=False,
    # ) -> ComponentT | None: ...

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


# class ReadPropertyContext(Protocol):
#     @property
#     def context(self) -> SapContext: ...
#     @property
#     def gateway(self) -> ComGateway: ...


class ReadPropertyMixin():
    _MISSING: ClassVar[object] = object()

    # No factory, no non-None default.
    @overload
    @staticmethod
    def get_property(
        dispatch: DispatchLike,
        prop: str,
        /,
        factory: None = None,
        *,
        default: None = None,
        source: str | None = None,
        _raise: Literal[False] = False,
    ) -> Any | None: ...

    # No factory, caller provides a default.
    @overload
    @staticmethod
    def get_property(
        dispatch: DispatchLike,
        prop: str,
        /,
        factory: None = None,
        *,
        default: T,
        source: str | None = None,
        _raise: bool = False,
    ) -> T | Any: ...

    # No factory, missing property raises.
    @overload
    @staticmethod
    def get_property(
        dispatch: DispatchLike,
        prop: str,
        /,
        factory: None = None,
        *,
        default: None = None,
        source: str | None = None,
        _raise: Literal[True],
    ) -> Any: ...

    # Factory supplied, missing property raises.
    @overload
    @staticmethod
    def get_property(
        dispatch: DispatchLike,
        prop: str,
        /,
        factory: Callable[[Any], T],
        *,
        default: T | None = None,
        source: str | None = None,
        _raise: Literal[True],
    ) -> T: ...

    # Factory supplied, missing property may return None.
    @overload
    @staticmethod
    def get_property(
        dispatch: DispatchLike,
        prop: str,
        /,
        factory: Callable[[Any], T],
        *,
        default: None = None,
        source: str | None = None,
        _raise: Literal[False] = False,
    ) -> T | None: ...

    # Factory supplied, missing property returns the provided default.
    @overload
    @staticmethod
    def get_property(
        dispatch: DispatchLike,
        prop: str,
        /,
        factory: Callable[[Any], T],
        *,
        default: T,
        source: str | None = None,
        _raise: bool = False,
    ) -> T: ...

    @staticmethod
    def get_property(
        dispatch: DispatchLike,
        prop: str,
        /,
        factory: Callable[[Any], T] | None = None,
        *,
        default: T | None = None,
        source: str | None = None,
        _raise: bool = False,
    ) -> Any:
        """Read a dynamic COM property with contextual error handling."""
        if not prop:
            raise ValueError("prop must not be empty")
        if source is None:
            source = "ReadProperty"
        try:
            value = getattr(dispatch, prop, ReadPropertyMixin._MISSING)
            if value is ReadPropertyMixin._MISSING:
                if _raise:
                    raise SapComError(
                        f"Property {prop!r} was not found on the dispatch object"
                    )
                return default
            if factory is None:
                return value
            return factory(value)
        except SapComError:
            raise
        except Exception as e:
            raise SapComError(
                LogMsg.err(
                    e,
                    f"Unable to read COM property {prop!r}",
                    dispatch=annotate(dispatch),
                    source=source,
                )
            ) from e