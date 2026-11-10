"""
*`@file`* `resin/gui/com/types`
"""

from __future__ import annotations

from typing import Any, Protocol

class DispatchLike(Protocol):
    """
    Structural type for a late-bound COM dispatch object.

    Individual SAP GUI object types expose additional members dynamically.
    """
    Id: str
    Type: str
    Parent: Any
    def __getattr__(self, attr: str) -> Any: ...
    def __setattr__(self, attr: str, value: Any) -> None: ...


class ChildrenLike(Protocol):
    Count: int
    def __call__(self, index: int) -> DispatchLike:
        ...
