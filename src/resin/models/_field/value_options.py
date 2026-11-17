"""
*`@file`* `models/_field/value_options`
"""
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field as _field
from typing import (Any, Self, TypedDict, TypeGuard)
from lute.message import LogMsg
from pyqi import (Json, export, Array, SupportsComparison)
from ._resolve import ( resolve_field_value)

_VALUE_RANGE_KEYS = frozenset(['lower', 'upper'])
def resolve_range_value(value: Any, /) -> Any:
    return _validate_range_value(resolve_field_value(value))


def _validate_range_value(value: Any, /) -> Any:
    if (value is None
        or isinstance(value, (Mapping, Set))
        or (isinstance(value, Sequence) and not isinstance(value, str))
        or not isinstance(value, SupportsComparison)
    ):
        raise ValueError(LogMsg.bad_arg(
            value, 
            "keyof ValueRange", 
            "ValueRange.lower and ValueRange.upper must support comparison",
            SupportsComparison
        ))
    return value

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
    def from_dict(
        cls, data: ValueRangeDict | dict[str, Any], /, *, resolve: bool = True
    ) -> Self:
        try:
            if not is_value_range_dict(data):
                raise ValueError("ValueRange requires exactly 'lower' and 'upper'")
            resolve_bound = resolve_range_value if resolve else _validate_range_value
            return cls(
                lower=resolve_bound(data['lower']),
                upper=resolve_bound(data['upper'])
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
    values: list[Any] = _field(default_factory=list)
    ranges: list[ValueRange] = _field(default_factory=list)

    @classmethod
    def from_dict(
        cls, data: MultiSelectionDict | dict[str, Any], /, *, resolve: bool = False
    ) -> Self:
        try:
            if isinstance(data, list): # TODO: mv to from_seq and add from_any
                singles: list[Any] = []
                ranges: list[ValueRange] = []
                for value in data:
                    if is_value_range_dict(value):
                        ranges.append(ValueRange.from_dict(value))
                    else:
                        singles.append(value)
                return cls(values=singles, ranges=ranges)
            return cls(
                values=[
                    resolve_field_value(v) if resolve else v
                    for v in data.get('values', [])
                ],
                ranges=[
                    ValueRange.from_dict(v, resolve=resolve)
                    for v in data.get('ranges', [])
                ]
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
    include: MultiSelectionDict | None
    exclude: MultiSelectionDict | None


def is_value_range_dict(value: Any, /) -> TypeGuard[ValueRangeDict]:
    """Check exact range keys; bounds are validated when constructing ValueRange."""
    return (
        isinstance(value, dict)
        and value.keys() == _VALUE_RANGE_KEYS
    )

def is_multi_selection_dict(value: Any, /) -> TypeGuard[MultiSelectionDict]:
    if (not isinstance(value, dict)): 
        return False
    _values = value.get('values', [])
    _ranges = value.get('ranges', [])
    return (value.keys() <= {'values', 'ranges'}
        and isinstance(_values, list)
        and isinstance(_ranges, list)
        and Array.every(_ranges, is_value_range_dict) 
    )

def is_value_options_dict(value: Any, /) -> TypeGuard[ValueOptionsDict]:
    if (not isinstance(value, dict)): 
        return False
    _include_val = value.get('include')
    _exclude_val = value.get('exclude')
    return (
        bool(value)
        and value.keys() <= {'include', 'exclude'}
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
    def from_dict(
        cls, 
        data: ValueOptionsDict | dict[str, Any], 
        /, 
        *, 
        resolve: bool = False
    ) -> Self:
        """Parse options; use resolve=False only for already evaluated definitions."""
        try:
            _include_val = data.get('include', data.get('values', None))
            _exclude_val = data.get('exclude')
            return cls(
                include=(
                    MultiSelection(values=_include_val) 
                        if isinstance(_include_val, list)
                    else MultiSelection.from_dict(_include_val, resolve=resolve) 
                        if isinstance(_include_val, dict)
                    else None
                ),
                exclude=(
                    MultiSelection.from_dict(_exclude_val, resolve=resolve)
                    if _exclude_val is not None
                    else None
                )
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                f"Failed to construct ValueOptions from dict object",
                received=Json.serialize(data)
            )) from e 

    @classmethod
    def from_sequence(
        cls, values: list[Any] | tuple[Any, ...], /, *, resolve: bool = True
    ) -> Self:
        """Treat range dictionaries as include.ranges and other entries as include.values."""
        if not isinstance(values, (list, tuple)):
            raise TypeError("ValueOptions.from_sequence requires a list or tuple")
        singles: list[Any] = []
        ranges: list[ValueRangeDict] = []
        for value in values:
            if is_value_range_dict(value):
                ranges.append(value)
            else:
                singles.append(value)
        return cls.from_dict(
            {'include': {'values': singles, 'ranges': ranges}},
            resolve=resolve,
        )


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