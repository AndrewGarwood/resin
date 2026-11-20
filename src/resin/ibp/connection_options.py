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
    # param_str: str

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
        # param_str: str | None = None
    ) -> None:
        self.name = name
        self.planning_area = planning_area
        self.server_url = server_url
        self.is_default = is_default
        # self.param_str = param_str

    @classmethod
    def from_dict(cls, data: ConnectionOptionsDict | dict[str, Any], /) -> Self:
        try:
            return cls(
                name=data['name'],
                planning_area=data.get("planning_area", None),
                server_url=data.get("server_url", None),
                is_default=data.get("is_default", True),
                # param_str=data.get('param_str', None),
            )
        except (ValueError, KeyError): raise
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
    # param_str: str | None = None

    @classmethod
    def from_options(cls, options: ConnectionOptions, /):
        return cls(
            name=options.name,
            planning_area=options.planning_area,
            server_url=options.server_url,
            # param_str=options.param_str
        )

__all__ = export(ConnectionOptions, ConnectionOptionsDict)