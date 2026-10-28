"""
*`@file`* `models/_field/_range`
"""
from dataclasses import dataclass
from typing import (Any, Self, TypedDict, TypeGuard)
from lute.message import LogMsg
from pyqi import (Json, export, Array, SupportsComparison)
from ._resolve import ( resolve_field_value)

_VALUE_RANGE_KEYS = frozenset(['lower', 'upper'])
def resolve_range_value(value: Any, /) -> Any:
    value = resolve_field_value(value)
    if (not isinstance(value, SupportsComparison)):
        raise ValueError(LogMsg.bad_arg(
            value, 
            "keyof ValueRange", 
            "ValueRange.lower and ValueRange.upper must support comparison",
            SupportsComparison
        ))

class ValueRangeDict(TypedDict):
    """ `(TypedDict)` """
    lower: Any
    upper: Any


@dataclass
class ValueRange(Json.Serial[ValueRangeDict]):
    """
    *`@extends`* `Json.Serial[ValueRangeDict]`
    """
    lower: SupportsComparison[Any]
    upper: SupportsComparison[Any]

    @classmethod
    def from_dict(cls, data: ValueRangeDict | dict[str, Any], /) -> Self:
        try:
            return cls(
                lower=resolve_range_value(data.get('lower')),
                upper=resolve_range_value(data.get('upper'))
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                f"Failed to construct ValueRange from dict object",
                received=Json.serialize(data)
            )) from e 

class MultiSelectionDict(TypedDict, total=False):
    """
    `TypedDict, total=False`
    """
    values: list[Any]
    ranges: list[ValueRangeDict]

@dataclass
class MultiSelection(Json.Serial[MultiSelectionDict]):
    """
    *`@extends`* `Json.Serial[MultiSelectionDict]`
    """
    values: list[Any]
    ranges: list[ValueRange]

    @classmethod
    def from_dict(cls, data: MultiSelectionDict | dict[str, Any], /) -> Self:
        try:
            return cls(
                values=Array.map(data.get('values', []), resolve_field_value),
                ranges=Array.map(data.get('ranges', []), ValueRange.from_dict)
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                f"Failed to construct MultiSelection from dict object",
                received=Json.serialize(data)
            )) from e 

class ValueOptionsDict(TypedDict, total=False):
    """
    `TypedDict, total=False`
    """
    include: MultiSelectionDict
    exclude: MultiSelectionDict


def is_value_range_dict(value: Any, /) -> TypeGuard[ValueRangeDict]:
    """ only checks that required keys are present, doesn't check if values are `None` """
    return (
        isinstance(value, dict)
        and Array.every(
            _VALUE_RANGE_KEYS, 
            lambda k: k in _VALUE_RANGE_KEYS
        )
    )

def is_multi_selection_dict(value: Any, /) -> TypeGuard[MultiSelectionDict]:
    if (not isinstance(value, dict)): 
        return False
    _values = value.get('values', [])
    _ranges = value.get('ranges', [])
    return (isinstance(_values, list)
        and isinstance(_ranges, list)
        and Array.every(_ranges, is_value_range_dict) 
    )

def is_value_options_dict(value: Any, /) -> TypeGuard[ValueOptionsDict]:
    if (not isinstance(value, dict)): 
        return False
    _include_val = value.get('include')
    _exclude_val = value.get('exclude')
    return (
        isinstance(value, dict)
        and (_include_val is None or is_multi_selection_dict(_include_val))
        and (_exclude_val is None or is_multi_selection_dict(_exclude_val))
    )

@dataclass
class ValueOptions(Json.Serial[ValueOptionsDict]):
    """
    *`@extends`* `Json.Serial[ValueOptionsDict]`
    """
    include: MultiSelection | None = None
    exclude: MultiSelection | None = None
    @classmethod
    def from_dict(cls, data: ValueOptionsDict | dict[str, Any], /) -> Self:
        try:
            _include_val = data.get('include')
            _exclude_val = data.get('exclude')
            return cls(
                include=(
                    MultiSelection.from_dict(_include_val) if _include_val 
                    else None
                ),
                exclude=(
                    MultiSelection.from_dict(_exclude_val) if _exclude_val 
                    else None
                )
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                f"Failed to construct ValueOptions from dict object",
                received=Json.serialize(data)
            )) from e 


__all__ = export(
    ValueOptionsDict, 
    ValueOptions, 
    MultiSelection, 
    MultiSelectionDict, 
    ValueRange, 
    ValueRangeDict,
    is_value_range_dict, 
    is_value_options_dict, 
    is_multi_selection_dict
)