"""
*`@file`* `ibp/binding`
"""
from dataclasses import dataclass
from typing import (Any, TypeVar, TypedDict, Protocol)
from pyqi import (BaseStrEnum, export)
from .connection_options import ConnectionIdentity

class BindingState(BaseStrEnum):
    """
    ```
    VALID = "valid"
    MISSING = "missing"
    EXPIRED = "expired"
    ```
    """
    VALID = "valid"
    MISSING = "missing"
    EXPIRED = "expired"

@dataclass(frozen=True)
class BindingObservation:
    """VALID means the verifier proved identity AND usable authentication."""
    state: BindingState
    identity: ConnectionIdentity | None = None



class BindingVerifier(Protocol):
    def __call__(
        self, 
        *, 
        workbook: Any, 
        worksheet: Any, 
        requested: ConnectionIdentity,
        connections: Any, 
        connect_result: Any,
    ) -> BindingObservation:
        """Validate installed API shapes; never return VALID from metadata alone."""
        ...


__all__ = export(BindingVerifier, BindingObservation, BindingState)