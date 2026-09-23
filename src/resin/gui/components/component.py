from __future__ import annotations

from typing import Any, Self

from .registry import wrap_dispatch

from ..com.gateway import ComGateway
from ..com.types import DispatchLike
from ..context import SapContext
from ..exceptions import SapComError

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
        # Validate immediately so invalid component wrappers cannot exist.
        context.require_component()

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
        return self._context.require_component()[0]

    @property
    def session_id(self) -> str:
        return self._context.require_component()[1]

    @property
    def id(self) -> str:
        return self._context.require_component()[2]

    @property
    def _com(self) -> DispatchLike:
        """
        Resolve the current COM object.

        Kept as a property for compatibility with your existing wrapper code.
        New code may prefer ``_resolve()`` because the operation is explicit.
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
        return self._read_string("Name")

    @property
    def type(self) -> str:
        return self._read_string("Type")

    @property
    def type_as_number(self) -> int:
        value = self._read("TypeAsNumber")

        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise SapComError(
                f"Component {self.id!r} returned invalid TypeAsNumber "
                f"value {value!r}"
            ) from exc

    @property
    def container_type(self) -> bool:
        return bool(self._read("ContainerType"))

    @property
    def parent(self) -> Component:
        parent_dispatch = self._read("Parent")

        if parent_dispatch is None:
            raise SapComError(
                f"Component {self.id!r} has no parent"
            )

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
        parent = self._read("Parent")

        if parent is None or not hasattr(parent, "Id"):
            raise SapComError(
                f"Component {self.id!r} returned an invalid parent object"
            )

        return parent

    def exists(self) -> bool:
        return self._gateway.component_exists(
            self.connection_id,
            self.session_id,
            self.id,
        )

    def set_focus(self) -> Self:
        dispatch = self._resolve()

        try:
            dispatch.SetFocus()
        except Exception as exc:
            raise SapComError(
                f"Unable to set focus on component {self.id!r}"
            ) from exc

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
        except Exception as exc:
            raise SapComError(
                f"Unable to visualize component {self.id!r}"
            ) from exc

        return self

    def diagnostic_state(self) -> dict[str, object]:
        """
        Safely collect commonly useful SAP GUI properties.

        This method is suitable for logging because an unavailable property
        does not abort collection of the remaining properties.
        """
        dispatch = self._resolve()
        properties = (
            "Id",
            "Name",
            "Type",
            "Text",
            "Changeable",
            "Enabled",
            "Visible",
            "ContainerType",
        )

        state: dict[str, object] = {}

        for property_name in properties:
            try:
                state[property_name] = getattr(dispatch, property_name)
            except Exception as exc:
                state[property_name] = (
                    f"<unavailable: {type(exc).__name__}: {exc}>"
                )

        return state

    def _read(self, property_name: str) -> Any:
        dispatch = self._resolve()

        try:
            return getattr(dispatch, property_name)
        except Exception as exc:
            raise SapComError(
                f"Unable to read property {property_name!r} from "
                f"component {self.id!r}"
            ) from exc

    def _read_string(self, property_name: str) -> str:
        value = self._read(property_name)

        if value is None:
            raise SapComError(
                f"Component {self.id!r} returned None for "
                f"{property_name!r}"
            )

        return str(value)

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} "
            f"connection_id={self.connection_id!r} "
            f"session_id={self.session_id!r} "
            f"id={self.id!r}>"
        )