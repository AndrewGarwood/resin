"""
*`@file`* `gui/models/connection_options`
"""
from pyqi import Json, export
from lute import LogMsg
from typing import Any, TypedDict, Self
from dataclasses import dataclass


class ConnectionOptionsDict(TypedDict, total=False):
    index: int | None
    id: str | None
    description: str | None
    string: str | None

@dataclass(frozen=True, slots=True, repr=False)
class ConnectionOptions(Json.Serial[ConnectionOptionsDict]):
    index: int | None  = None
    id: str | None  = None
    description: str | None = None
    string: str | None = None

    @classmethod
    def from_dict(cls, data: ConnectionOptionsDict | dict[str, Any] | str, ) -> Self:
        """
        if `data` is `str` return `cls(description=data)` (assume it's the description str)
        """
        try:
            if (isinstance(data, str)):
                return cls(description=data)
            return cls(
                index=data.get('index'),
                id=data.get('id'),
                description=data.get('description'),
                string=data.get('string'),
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                "Failed to construct SAPGUI ConnectionOptions",
                received=Json.serialize(data)
            )) from e


__all__ = export(ConnectionOptionsDict, ConnectionOptions)