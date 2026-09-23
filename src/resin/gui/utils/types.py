"""
*`@file`* `resin/gui/utils/types`
"""

from typing import Any, TypeVar, Protocol, runtime_checkable
import lute
LogMsg = lute.LogMsg
V = TypeVar('V', contravariant=True)

T = TypeVar("T")

@runtime_checkable
class HasSession(Protocol):
    @property
    def session(self) -> Any:
        ...


@runtime_checkable
class HasSetter(Protocol[V]):
    def set(self, value: V) -> Any:
        ...

def require_non_empty_string(
    value: str,
    /,
    name: str='arg',
) -> None:
    if (not isinstance(value, str) or not value.strip()):
        raise ValueError(LogMsg.bad_arg(
            value, name, "Non-empty string is required", str
        ))

def require_positive_number(
    value: int | float,
    /,
    name: str,
) -> int | float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))):
        raise TypeError(LogMsg.bad_arg(
            value, name, "Number required.", int, float
        ))

    if value <= 0:
        raise ValueError(LogMsg.bad_arg(
            value, name, "Positive number required.", int, float
        ))

    return value

