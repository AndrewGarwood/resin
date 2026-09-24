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
