"""

"""
from typing import (Any, Literal, Optional, TypeVar, overload, Protocol)
import lute

from resin.gui.components.registry import wrap_dispatch
from resin.gui.exceptions import SapComError, SapGuiError
LogMsg = lute.LogMsg
from .components.component import Component
from .com.gateway import ComGateway
from .context import SapContext
ComponentT = TypeVar("ComponentT", bound=Component)

class FindAttributes(Protocol):
    @property
    def context(self) -> SapContext: ...
    @property
    def gateway(self) -> ComGateway: ...
    @property
    def id(self) -> str: ...
    @property
    def component_id(self) -> str: ...
    @property
    def session_id(self) -> str: ...
    @property
    def connection_id(self) -> str: ...
#     @overload
#     def find(
#         self,
#         component_id: str,
#         /,
#         *,
#         component_cls: None = None,
#         _raise: Literal[False] = False,
#     ) -> Component | None: ...

#     @overload
#     def find(
#         self,
#         component_id: str,
#         /,
#         *,
#         component_cls: None = None,
#         _raise: Literal[True],
#     ) -> Component: ...

#     @overload
#     def find(
#         self,
#         component_id: str,
#         /,
#         *,
#         component_cls: type[ComponentT],
#         _raise: Literal[True]=True,
#     ) -> ComponentT:
#         ...

#     @overload
#     def find(
#         self,
#         component_id: str,
#         /,
#         *,
#         component_cls: type[ComponentT],
#         _raise: Literal[False] = False,
#     ) -> ComponentT | None:
#         ...

#     @overload
#     def find(
#         self,
#         component_id: str,
#         /,
#         *,
#         component_cls: None = None,
#         _raise: bool,
#     ) -> Component | None: ...

#     @overload
#     def find(
#         self,
#         component_id: str,
#         /,
#         *,
#         component_cls: type[ComponentT],
#         _raise: bool,
#     ) -> ComponentT | None: ...

#     def find(
#         self,
#         component_id: str,
#         /,
#         *,
#         component_cls: type[ComponentT] | None = None,
#         _raise: bool = False,
#     ) -> Component | ComponentT | None:
#         if not isinstance(component_id, str) or not component_id.strip():
#             raise ValueError(
#                 LogMsg(
#                     "Invalid SAP GUI component ID",
#                     expected="non-empty str",
#                     received=lute.annotate(component_id),
#                 )
#             )

#         if component_cls is not None and (
#             not isinstance(component_cls, type)
#             or not issubclass(component_cls, Component)
#         ):
#             raise TypeError(
#                 LogMsg(
#                     "Invalid SAP GUI component wrapper class",
#                     expected="Component subclass",
#                     received=lute.annotate(component_cls),
#                 )
#             )

#         try:
#             obj = self.gateway.find_component(
#                 self.connection_id,
#                 self.session_id,
#                 component_id,
#                 raise_on_missing=_raise,
#             )

#             if obj is None:
#                 return None

#             if component_cls is None:
#                 return wrap_dispatch(
#                     obj,
#                     gateway=self.gateway,
#                     context=self.context,
#                 )

#             try:
#                 actual_id = str(obj.Id)
#             except Exception as e:
#                 raise SapComError(
#                     LogMsg.err(
#                         e,
#                         "Resolved SAP GUI component has no usable ID",
#                         requested_component_id=component_id,
#                         dispatch=lute.annotate(obj),
#                     )
#                 ) from e

#             return component_cls(
#                 gateway=self.gateway,
#                 context=self.context.with_component(actual_id),
#             )

#         except SapGuiError:
#             raise
#         except Exception as e:
#             raise SapComError(
#                 LogMsg.err(
#                     e,
#                     "Unable to find SAP GUI component",
#                     component_id=component_id,
#                     component_cls=(
#                         None
#                         if component_cls is None
#                         else (
#                             f"{component_cls.__module__}."
#                             f"{component_cls.__qualname__}"
#                         )
#                     ),
#                     raise_on_missing=_raise,
#                     container_id=self.id,
#                     connection_id=self.connection_id,
#                     session_id=self.session_id,
#                 )
#             ) from e


class FindMixin:
    gateway: Any
    context: Any
    connection_id: str
    session_id: str

    @overload
    def find(
        self,
        component_id: str,
        /,
        *,
        component_cls: None = None,
        _raise: Literal[False] = False,
    ) -> Component | None:
        ...

    @overload
    def find(
        self,
        component_id: str,
        /,
        *,
        component_cls: None = None,
        _raise: Literal[True],
    ) -> Component:
        ...

    @overload
    def find(
        self,
        component_id: str,
        /,
        *,
        component_cls: type[ComponentT],
        _raise: Literal[False] = False,
    ) -> ComponentT | None:
        ...

    @overload
    def find(
        self,
        component_id: str,
        /,
        *,
        component_cls: type[ComponentT],
        _raise: Literal[True],
    ) -> ComponentT:
        ...

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

            if obj is None:
                return None

            if component_cls is None:
                return wrap_dispatch(
                    obj,
                    gateway=self.gateway,
                    context=self.context,
                )

            return component_cls(
                gateway=self.gateway,
                context=self.context.with_component(
                    str(obj.Id)
                ),
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