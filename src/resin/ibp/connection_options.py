"""
*`@file`* `ibp/connection_options`
"""
from dataclasses import dataclass
from typing import (TypedDict, Any, Self, Required)
from pyqi import (Json, export)
from lute import LogMsg



class ConnectionIdentityDict(TypedDict, total=False):
    """ `TypedDict, total=False` """
    name: Required[str]
    planning_area: str
    server_url: str
    is_default: bool
    
class ConnectionOptionsDict(ConnectionIdentityDict, total=False):
    """ *`@extends`* `ConnectionIdentityDict` """
    is_default: bool

class ConnectionOptions(Json.Serial[ConnectionOptionsDict]):
    """
    *`@extends`* `Json.Serial[ConnectionOptionsDict]`
    """
    name: str
    planning_area: str | None = None
    server_url: str | None = None
    is_default: bool = True
    # param_str: str | None = None
    # """
    # - can obtained after `Controller.ibp.Connect(<ConnectionOptions.name>)`
    # - = `'{<str>}_[<server_url>]_[<str>]_[<planning_area>]_[]_[]_[<bool>]_[<bool>]'` 
    # """

    def __init__(
        self, 
        name: str, 
        planning_area: str | None = None,
        server_url: str | None = None,
        is_default: bool = True,
    ) -> None:
        self.name = name
        self.planning_area = planning_area
        self.server_url = server_url
        self.is_default = is_default

    @classmethod
    def from_dict(cls, data: ConnectionOptionsDict | dict[str, Any], /) -> Self:
        try:
            return cls(
                name=data['name'],
                planning_area=data.get("planning_area", None),
                server_url=data.get("server_url", None),
                is_default=data.get("is_default", True),
            )
        except (ValueError, KeyError): raise
        except Exception as e:
            raise RuntimeError(LogMsg.err(e,
                f"Failed to construct ibp.ConnectionOptions from dict",
                received=Json.serialize(data)
            )) from e


@dataclass(frozen=True)
class ConnectionIdentity(Json.Serial[ConnectionIdentityDict]):
    """
    - `@dataclass(frozen=True)`
    - *`@extends`* `Json.Serial[ConnectionIdentityDict]`
    """
    name: str
    planning_area: str | None = None
    server_url: str | None = None

    @classmethod
    def from_options(cls, options: ConnectionOptions, /):
        return cls(
            name=options.name,
            planning_area=options.planning_area,
            server_url=options.server_url,
        )

    @classmethod
    def from_dict(cls, data: ConnectionIdentityDict | dict[str, Any], /) -> Self:
        return cls(
            name=data['name'],
            planning_area=data.get("planning_area", None),
            server_url=data.get("server_url", None),
        )

    def to_dict(self) -> ConnectionIdentityDict | dict[str, Any]:
        return {
            "name": self.name,
            "planning_area": self.planning_area,
            "server_url": self.server_url,
        }

__all__ = export(
    ConnectionOptions, 
    ConnectionOptionsDict,
    ConnectionIdentity,
    ConnectionIdentityDict
)