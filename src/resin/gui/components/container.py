from __future__ import annotations

from collections.abc import Iterator
from typing import (Any, Literal, Optional, Type, TypeVar, overload, Generic)
import lute
from pyqi import Array
from ..com.gateway import ComGateway
from ..context import SapContext
from ..exceptions import (
    SapComponentNotFoundError,
    SapComError,
    SapGuiError,
)
from .component import Component
from .registry import wrap_dispatch, generate_sap_type
from .._supports_find import FindMixin

LogMsg = lute.LogMsg
ComponentT = TypeVar("ComponentT", bound=Component)
ChildT = TypeVar("ChildT", bound=Component)

class Container(Component, Generic[ChildT]):
    """
    Base wrapper for session-bound components supporting FindById.

    This class intentionally represents only component containers. Application
    and Connection should not inherit this class because they are not bound to
    one session and cannot safely use session-based FindById operations.
    """

    def __init__(
        self,
        *,
        gateway: ComGateway,
        context: SapContext,
    ) -> None:
        super().__init__(
            gateway=gateway,
            context=context,
        )

    @property
    def children(self) -> tuple[ChildT, ...]:
        """
        Return wrapped immediate children.

        A tuple is returned so callers do not mistake the result for a live
        mutable SAP GUI collection.
        """
        dispatch = self._resolve()

        try:
            com_children = dispatch.Children
            count = int(com_children.Count)
        except Exception as e:
            raise SapComError(
                f"Unable to enumerate children of component {self.id!r}"
            ) from e

        children: list[ChildT] = []

        for index in range(count):
            try:
                child_dispatch = com_children(index)
            except Exception as e:
                raise SapComError(
                    f"Unable to read child {index} of component {self.id!r}"
                ) from e

            if child_dispatch is None:
                raise SapComError(
                    f"Child {index} of component {self.id!r} was None"
                )

            children.append(
                wrap_dispatch(
                    child_dispatch,
                    gateway=self.gateway,
                    context=self.context,
                )
            )

        return tuple(children)

    def iter_children(self) -> Iterator[ChildT]:
        """
        Iterate through the current child snapshot.

        The snapshot behavior avoids holding a live COM collection while user
        code is running.
        """
        yield from self.children


    @overload
    def find(
        self,
        component_id: str,
        /,
        *,
        component_cls: None = None,
        _raise: Literal[False] = False,
    ) -> Component | None: ...

    @overload
    def find(
        self,
        component_id: str,
        /,
        *,
        component_cls: None = None,
        _raise: Literal[True],
    ) -> Component: ...

    @overload
    def find(
        self,
        component_id: str,
        /,
        *,
        component_cls: type[ComponentT],
        _raise: Literal[True]=True,
    ) -> ComponentT:
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
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError(
                LogMsg(
                    "Invalid SAP GUI component ID",
                    expected="non-empty str",
                    received=lute.annotate(component_id),
                )
            )

        if component_cls is not None and (
            not isinstance(component_cls, type)
            or not issubclass(component_cls, Component)
        ):
            raise TypeError(
                LogMsg(
                    "Invalid SAP GUI component wrapper class",
                    expected="Component subclass",
                    received=lute.annotate(component_cls),
                )
            )

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

            try:
                actual_id = str(obj.Id)
            except Exception as e:
                raise SapComError(
                    LogMsg.err(
                        e,
                        "Resolved SAP GUI component has no usable ID",
                        requested_component_id=component_id,
                        dispatch=lute.annotate(obj),
                    )
                ) from e

            return component_cls(
                gateway=self.gateway,
                context=self.context.with_component(actual_id),
            )

        except SapGuiError:
            raise
        except Exception as e:
            raise SapComError(
                LogMsg.err(
                    e,
                    "Unable to find SAP GUI component",
                    component_id=component_id,
                    component_cls=(
                        None
                        if component_cls is None
                        else (
                            f"{component_cls.__module__}."
                            f"{component_cls.__qualname__}"
                        )
                    ),
                    raise_on_missing=_raise,
                    container_id=self.id,
                    connection_id=self.connection_id,
                    session_id=self.session_id,
                )
            ) from e


    def exists(
        self,
        component_id: str | None = None,
        /,
    ) -> bool:
        """
        Check this container or one descendant.

        ``container.exists()`` checks whether this container still exists.
        ``container.exists("wnd[0]/usr/...")`` checks a descendant.
        """
        if component_id is None:
            return super().exists()

        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError(
                "component_id must be a non-empty string"
            )

        return self.gateway.component_exists(
            self.connection_id,
            self.session_id,
            component_id,
        )