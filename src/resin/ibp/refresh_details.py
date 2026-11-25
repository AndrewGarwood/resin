"""
*`@file`* `ibp/refresh_details`
"""
from dataclasses import dataclass
from typing import (Any, Self, TypedDict, Required)
from pyqi import (Json, export)
from .connection_options import (ConnectionIdentity, ConnectionIdentityDict)


class RefreshDetailsDict(TypedDict, total=False):
    requested_connection: Required[ConnectionIdentityDict]
    observed_connection: ConnectionIdentityDict | None
    connection_called: bool
    binding_reused: bool | None


@dataclass(frozen=True, repr=False)
class RefreshDetails(Json.Serial[RefreshDetailsDict]):
    """
    - `@dataclass(frozen=True, repr=False)`
    - *`@extends`* `Json.Serial[RefreshDetailsDict]`
    """
    requested_connection: ConnectionIdentity
    observed_connection: ConnectionIdentity | None
    connect_called: bool
    binding_reused: bool | None = None


    @classmethod
    def from_dict(cls, data: RefreshDetailsDict | dict[str, Any], /) -> Self:
        _observed = data.get('observed_connection')
        return cls(
            requested_connection=ConnectionIdentity.from_dict(data['requested_connection']),
            observed_connection=ConnectionIdentity.from_dict(_observed) if _observed else None,
            connect_called=data.get('connect_called', False),
            binding_reused=data.get('binding_reused')
        )

    def to_dict(self):
        return {
            "requested_connection": self.requested_connection.to_dict(),
            "observed_connection": (
                self.observed_connection.to_dict() 
                if self.observed_connection 
                else None
            ),
            "connect_called": self.connect_called,
            "binding_reused": self.binding_reused
        }

__all__ = export(RefreshDetails, RefreshDetailsDict)