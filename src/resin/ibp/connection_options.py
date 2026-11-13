"""
*`@file`* `ibp/connection_options`
"""
from dataclasses import dataclass
from typing import (TypedDict, Any, Self, Required)
from pyqi import (Json, require, export)
from lute import LogMsg



class ConnectionOptionsDict(TypedDict, total=False):
    """ `TypedDict, total=False` """
    name: Required[str]
    planning_area: str
    server_url: str
    is_default: bool
    connstr: str # TODO: rename this to infostr or connstr or something b/c value read may not actually be the id


class ConnectionOptions(Json.Serial[ConnectionOptionsDict]):
    """
    *`@extends`* `Json.Serial[ConnectionOptionsDict]`
    """
    name: str
    planning_area: str | None = None
    server_url: str | None = None
    is_default: bool = True
    _connstr: str | None = None

    def __init__(
        self, 
        name: str, 
        planning_area: str | None = None,
        server_url: str | None = None,
        is_default: bool = True,
        connstr: str | None = None
    ) -> None:
        self.name = name
        self.planning_area = planning_area
        self.server_url = server_url
        self.is_default = is_default
        self._connstr = connstr

    @property
    def connstr(self) -> str:
        if (not self._connstr):
            raise RuntimeError(f"self._connstr is undefined")
        return self.connstr
    @connstr.setter
    def connstr(self, value: str, /):
        self._connstr = require.non_empty_string(value, 'connstr')

    @classmethod
    def from_dict(cls, data: ConnectionOptionsDict | dict[str, Any], /) -> Self:
        try:
            return cls(
                name=data['name'],
                planning_area=data.get("planning_area", None),
                server_url=data.get("server_url", None),
                is_default=data.get("is_default", True),
                connstr=data.get('connstr', data.get('id', None)),
            )
        except (ValueError, KeyError): 
            raise
        except Exception as e:
            raise RuntimeError(LogMsg.err(e,
                f"Failed to construct ibp.ConnectionOptions from dict",
                received=Json.serialize(data)
            )) from e

@dataclass(frozen=True)
class ConnectionIdentity:
    name: str
    planning_area: str | None = None
    server_url: str | None = None
    connstr: str | None = None

__all__ = export(ConnectionOptions, ConnectionOptionsDict)