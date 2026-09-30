"""
*`@file`* `resin/gui/utils/types`
"""

from typing import (Any, TypeVar, Protocol, runtime_checkable)
from pyqi import export
import lute
LogMsg = lute.LogMsg
V = TypeVar('V', contravariant=True)

T = TypeVar("T")

@runtime_checkable
class HasSession(Protocol):
    @property
    def session(self) -> Any: ...

@runtime_checkable
class SupportsSet(Protocol[V]):
    def set(self, value: V) -> Any: ...

@runtime_checkable
class SupportsPress(Protocol):
    def press(self) -> Any: ...

@runtime_checkable
class SupportsSelect(Protocol):
    def select(self) -> Any: ...

__all__ = export(HasSession, SupportsSet, SupportsPress, SupportsSelect)