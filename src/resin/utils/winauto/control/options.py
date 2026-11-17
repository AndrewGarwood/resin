"""
*`@file`* `utils/winauto/control/options`
"""
from __future__ import annotations
from typing import (Self, TypedDict, Any)
from pyqi import (Json, Arbitrary, resolve_arbitrary, Array, export)
from .types import ControlClass



class ControlOptionsDict(TypedDict, total=False):
    class_name: ControlClass | str
    title_re: Arbitrary[str]
    title: Arbitrary[str]
    visible_only: bool

class ControlOptions(Json.Serial[ControlOptionsDict]):
    """
    *`@extends`* `Serial[ControlOptionsDict]`
    """
    def __init__(
        self, 
        class_name: ControlClass | str | None=None, 
        title_re: Arbitrary[str] | None=None, 
        title: Arbitrary[str] | None=None, 
        visible_only: bool | None=None
    ):
        self._class_name = class_name
        self._title_patterns = Array.filter(resolve_arbitrary(title_re), None)
        self._titles = Array.filter(resolve_arbitrary(title), None)
        self.visible_only = (
            visible_only if visible_only is not None 
            else True
        )

    @property
    def title_re(self) -> str:
        """ *`@returns`* `r'|'.join(self._title_patterns)`  """
        return r"|".join(self._title_patterns)

    @property
    def composite_title_re(self) -> str:
        """ *`@returns`* `r'|'.join([*self._title_patterns, *self._titles])`  """
        arr = list(self._title_patterns)
        arr.extend(self._titles)
        return r"|".join(arr)

    @property
    def class_name(self) -> str:
        if (not self._class_name):
            raise RuntimeError(f"self._class_name is undefined")
        return str(self._class_name)
    @property
    def type(self) -> str: 
        return self.class_name

    # def to_dict(self) -> ControlOptionsDict | dict[str, Any]:
    #     result: ControlOptionsDict = {
    #         "class_name": self.class_name,
    #         "title_re": self.title_re,
    #         "title": self.title
    #     }
    #     return {}

    @classmethod
    def from_dict(cls, data: ControlOptionsDict | dict[str, Any], /) -> Self:
        return cls(
            class_name=data.get('class_name'),
            title_re=data.get('title_re'),
            title=data.get('title'),
            visible_only=data.get('visible_only'),
        )

__all__ = export(ControlOptionsDict, ControlOptions)