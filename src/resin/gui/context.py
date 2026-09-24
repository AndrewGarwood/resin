"""
*`@file`* `resin/gui/context`
- immutable application, connection, session, and component IDs.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .exceptions import SapInvalidContextError


@dataclass(frozen=True, slots=True)
class SapContext:
    """
    Stable identity for an SAP GUI wrapper.

    Dispatch objects are deliberately not stored here. They are resolved from
    the IDs on the thread performing the operation.
    """

    application_id: str | None = None
    connection_id: str | None = None
    session_id: str | None = None
    component_id: str | None = None

    def __post_init__(self) -> None:
        values = {
            "application_id": self.application_id,
            "connection_id": self.connection_id,
            "session_id": self.session_id,
            "component_id": self.component_id,
        }
        for name, value in values.items():
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ValueError(
                    f"{name} must be a non-empty string or None; "
                    f"received {value!r}"
                )
        if (self.session_id is not None and self.connection_id is None):
            raise ValueError(
                "session_id cannot be provided without connection_id"
            )
        if (self.component_id is not None and self.session_id is None):
            raise ValueError(
                "component_id cannot be provided without session_id"
            )

    def with_application(self, application_id: str, /) -> SapContext:
        return replace(self, application_id=application_id)

    def with_connection(self, connection_id: str, /) -> SapContext:
        return replace(
            self,
            connection_id=connection_id,
            session_id=None,
            component_id=None,
        )

    def with_session(self, session_id: str, /) -> SapContext:
        if self.connection_id is None:
            raise SapInvalidContextError(
                "Cannot add a session ID without a connection ID"
            )
        return replace(
            self,
            session_id=session_id,
            component_id=None,
        )

    def with_component(self, component_id: str, /) -> SapContext:
        if self.connection_id is None or self.session_id is None:
            raise SapInvalidContextError(
                "Cannot add a component ID without connection and session IDs"
            )

        return replace(self, component_id=component_id)

    def require_connection(self) -> str:
        if (not self.connection_id):
            raise SapInvalidContextError(
                "This operation requires a connection ID"
            )
        return self.connection_id
    
    def get_connection_id(self) -> str:
        return self.require_connection()

    def require_session(self) -> tuple[str, str]:
        """ 
        - *`@returns`* `(connection_id, session_id)`
        - *`@throws`* `SapInvalidContextError` if not `self.session_id`
        """
        connection_id = self.require_connection()
        if (not self.session_id):
            raise SapInvalidContextError(
                "This operation requires a session ID"
            )
        return connection_id, self.session_id
    
    def get_session_id(self) -> str:
        return self.require_session()[1]

    def require_component(self) -> tuple[str, str, str]:
        """ 
        - *`@returns`* `(connection_id, session_id, self.component_id)`
        - *`@throws`* `SapInvalidContextError` if not `self.component_id`
        """
        connection_id, session_id = self.require_session()
        if (not self.component_id):
            raise SapInvalidContextError(
                "This operation requires a component ID"
            )
        return (connection_id, session_id, self.component_id)
    
    def get_component_id(self) -> str:
        return self.require_component()[2]