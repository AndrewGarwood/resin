"""
*`@file`* `gui/components/component`
- [SAP GuiComponent](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/8ba9356d3c524ee2b3ded3f97b0a86ba.html)
- [SAP GuiVComponent](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/26824bb464b045558bf5c71a617aa7fb.html).
"""
from __future__ import annotations

from typing import (TYPE_CHECKING, Any, Self, Sequence)
from pyqi import export

from .registry import wrap_dispatch
from ..com.gateway import ComGateway
from ..com.types import DispatchLike
from ..context import SapContext
from ..exceptions import SapComError

if TYPE_CHECKING:
    from ..core.session import Session

class Component:
    """
    Base wrapper for a session-bound SAP GUI component.

    Components retain stable SAP IDs, not a child COM dispatch object. The
    dispatch object is resolved for each operation on the calling thread.
    """

    def __init__(
        self,
        *,
        gateway: ComGateway,
        context: SapContext,
    ) -> None:
        context.require_component() # raise if invalid component wrapper
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
    def session_id(self) -> str:
        return self._context.get_session_id()

    @property
    def id(self) -> str:
        return self._context.get_component_id()

    @property
    def _com(self) -> DispatchLike:
        """
        Resolve the current COM object.

        Kept as a property for compatibility with existing code.
        - New code may prefer ``_resolve()`` because the operation is explicit.
        """
        return self._resolve()

    def _resolve(self) -> DispatchLike:
        connection_id, session_id, component_id = (
            self._context.require_component()
        )
        result = self._gateway.find_component(
            connection_id,
            session_id,
            component_id,
            raise_on_missing=True,
        )
        # ``raise_on_missing=True`` guarantees a dispatch object.
        if result is None:
            raise SapComError(
                f"Component resolution unexpectedly returned None: "
                f"{component_id!r}"
            )
        return result

    @property
    def session(self) -> Session:
        """
        Return a session wrapper for this component.

        The local import avoids a component -> session -> component import
        cycle during module initialization.
        """
        from ..core.session import Session
        return Session(
            gateway=self._gateway,
            context=SapContext(
                application_id=self._context.application_id,
                connection_id=self.connection_id,
                session_id=self.session_id,
            ),
        )

    @property
    def name(self) -> str:
        return self._gateway.get_property(
            self._resolve(), "Name", str, 
            _raise=True, 
            source=self.__class__.__name__
        )

    @property
    def type(self) -> str:
        return self._gateway.get_property(
            self._resolve(), "Type", str, 
            _raise=True, 
            source=self.__class__.__name__
        )

    @property
    def type_as_number(self) -> int:
        return self._gateway.get_property(
            self._resolve(), "TypeAsNumber", int, 
            _raise=True, 
            source=self.__class__.__name__
        )
    
    @property
    def container_type(self) -> bool:
        return self._gateway.get_property(
            self._resolve(), 
            "ContainerType", 
            bool, 
            _raise=True, 
            source=self.__class__.__name__
        )

    @property
    def parent(self) -> Component:
        parent_dispatch = self.com_parent
        try:
            parent_id = str(parent_dispatch.Id)
        except Exception as exc:
            raise SapComError(
                f"Parent of component {self.id!r} has no usable ID"
            ) from exc


        return wrap_dispatch(
            parent_dispatch,
            gateway=self._gateway,
            context=self._context.with_component(parent_id),
        )

    @property
    def com_parent(self) -> DispatchLike:
        """
        Return the raw parent dispatch object.

        Prefer ``parent`` in library code. This property exists for operations
        that cannot yet be represented by a wrapper.
        """
        parent_dispatch = self._gateway.get_property(self._resolve(), "Parent", _raise=True)

        if (parent_dispatch is None or not hasattr(parent_dispatch, "Id")):
            raise SapComError(
                f"Component {self.id!r} returned an invalid parent object"
            )
        return parent_dispatch

    def exists(self) -> bool:
        return self._gateway.component_exists(
            self.connection_id,
            self.session_id,
            self.id,
        )


    def diagnostic_state(
        self, 
        properties: Sequence[str]=[
            "Id",
            "Name",
            "Type",
            "Text",
            "Changeable",
            "Enabled",
            "Visible",
            "ContainerType"
        ]
    ) -> dict[str, object]:
        """
        Safely collect commonly useful SAP GUI properties.

        This method is suitable for logging because an unavailable property
        does not abort collection of the remaining properties.
        """
        dispatch = self._resolve()
        state: dict[str, object] = {}
        for property_name in properties:
            try:
                state[property_name] = getattr(dispatch, property_name)
            except Exception as e:
                state[property_name] = (
                    f"<unavailable: {type(e).__name__}: {e}>"
                )
                continue
        return state

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} "
            f"connection_id={self.connection_id!r} "
            f"session_id={self.session_id!r} "
            f"id={self.id!r}>"
        )


class VComponent(Component):
    """
    "The GuiVComponent interface is exposed by all visual objects, such as windows, buttons or text fields."
    - [SAP GuiVComponent](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/26824bb464b045558bf5c71a617aa7fb.html).
    """
    @property
    def text(self) -> str:
        return self._gateway.get_property(self._resolve(), "Text", str, _raise=True, source=self.__class__.__name__)

    @property
    def changeable(self) -> bool:
        return self._gateway.get_property(self._resolve(), "Changeable", bool, _raise=True, source=self.__class__.__name__)

    @property
    def enabled(self) -> bool:
        return self._gateway.get_property(self._resolve(), "Enabled", bool, _raise=True, source=self.__class__.__name__)

    def dump_state(self, inner_obj: str="") -> Any:
        return self._resolve().DumpState(inner_obj)


    def set_focus(self) -> Self:
        dispatch = self._resolve()
        try:
            dispatch.SetFocus()
        except Exception as e:
            raise SapComError(
                f"Unable to set focus on component {self.id!r}"
            ) from e
        return self


    def visualize(
        self,
        enabled: bool = True,
        inner_object: str = "",
    ) -> Self:
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a bool")
        if not isinstance(inner_object, str):
            raise TypeError("inner_object must be a string")

        dispatch = self._resolve()
        try:
            dispatch.Visualize(enabled, inner_object)
        except Exception as e:
            raise SapComError(
                f"Unable to visualize component {self.id!r}"
            ) from e

        return self


__all__ = export(Component, VComponent)
