"""
*`@file`* `resin/gui/utils/types`
"""

from typing import Any, TypeVar, Protocol, runtime_checkable

V = TypeVar('V', contravariant=True)

@runtime_checkable
class HasSession(Protocol):
    @property
    def session(self) -> Any:
        ...


@runtime_checkable
class HasSetter(Protocol[V]):
    def set(self, value: V) -> Any:
        ...
