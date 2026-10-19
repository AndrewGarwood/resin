"""
*`@file`* `gui/services/transaction/multiple_selection`
- SAPGUI ctxt multiple selection window options
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import (Any, Self, TypeVar, TypedDict, TypeGuard, Generic)
from lute.message import LogMsg
from pyqi import (Json, export, Array, SupportsComparison)
from resin.models._field import (
    resolve_sentinel_value_dict, 
    resolve_field_value,
    is_sentinel_value_dict,
    SENTINEL_FUNCTION_REGISTRY
)
VT = TypeVar('VT', bound=SupportsComparison)


_VALUE_RANGE_KEYS = frozenset(['lower', 'upper'])
class ValueRangeDict(TypedDict):
    """ `(TypedDict)` """
    lower: Any
    upper: Any

def is_value_range_dict(value: Any, /) -> TypeGuard[ValueRangeDict]:
    """ only checks that required keys are present, doesn't check if values are `None` """
    return (
        isinstance(value, Mapping)
        and Array.every(
            _VALUE_RANGE_KEYS, lambda k: k in _VALUE_RANGE_KEYS
        )
    )

def resolve_range_value(value: Any, /) -> Any:
    if (is_sentinel_value_dict(value)):
        if (SENTINEL_FUNCTION_REGISTRY.is_registered(value['sentinel'])):
            return resolve_sentinel_value_dict(value)
        raise ValueError("Unsupported SentinelKey encountered in RangeValue.values()")
    if (not isinstance(value, SupportsComparison)):
        raise ValueError(LogMsg.bad_arg(
            value, 
            "RangeValue.values()[i]", 
            "RangeValue values must support comparison to be used as lower or upper bounds",
            SupportsComparison
        ))


@dataclass
class ValueRange(Json.Serial[ValueRangeDict], Generic[VT]):
    lower: VT
    upper: VT



    @classmethod
    def from_dict(cls, data: ValueRangeDict | dict[str, Any]) -> Self:
        try:
            raise NotImplementedError
            lower_val = data['lower']
            if (is_sentinel_value_dict(lower_val) 
                and SENTINEL_FUNCTION_REGISTRY.is_registered(lower_val['sentinel'])
            ):
                lower_val = resolve_sentinel_value_dict(lower_val)

            upper_val = data['upper']
            return cls(
                lower=data['lower'],
                upper=data['upper']
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, received=Json.serialize(data)
            )) from e 
        
        raise NotImplementedError

class MultipleSelectionDict(TypedDict):
    values: list[Any]
    ranges: list[ValueRangeDict]

class MultipleSelection(Json.Serial[MultipleSelectionDict]):
    values: list[str]
    ranges: list[ValueRangeDict]