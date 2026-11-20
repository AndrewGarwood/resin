"""
*`@file`* `ibp/binding`
"""
from dataclasses import dataclass
from typing import (Any, Protocol)
from win32com.client import CDispatch
from pyqi import (BaseStrEnum, export, guard, String)
from .connection_options import ConnectionIdentity
from resin._workbook.exceptions import (ConnectionBindingError)
from lute import LogMsg

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
        requested: ConnectionIdentity,
        active_connection: str | Any,
        *, 
        workbook: CDispatch | None=None, 
        worksheet: CDispatch | None=None, 
        connections: Any | None = None, 
    ) -> BindingObservation: ...
    """Validate installed API shapes; never return VALID from metadata alone."""
        


def naive_binding_verifier(
    requested: ConnectionIdentity, 
    active_connection: str | Any,
    **kwargs
) -> BindingObservation:
    
    if (not active_connection or not guard.is_non_empty_string(active_connection)):
        return BindingObservation(BindingState.MISSING, requested)
    _substrings = [
        x for x in (requested.planning_area, requested.server_url) 
        if bool(x)
    ]
    if (not _substrings):
        raise ConnectionBindingError(LogMsg(
            f"Invalid ConnectionIdentity for binding verification",
            f"Must define at least one of planning_area, server_url",
        ))
    if (String.contains(active_connection, _substrings, require_all=True)):
        return BindingObservation(BindingState.VALID, requested)
    return BindingObservation(BindingState.MISSING, None)

def default_connect_result_verifier(value: Any, /) -> bool:
    return (
        value == None 
        or
        (isinstance(value, (bool, int)) and value == 1) 
    )


__all__ = export(
    BindingVerifier, 
    BindingObservation, 
    BindingState, 
    default_connect_result_verifier,
    naive_binding_verifier
)