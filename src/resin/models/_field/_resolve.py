"""
*`@file`* `models/_field/_resolve`
"""
from typing import Any, Mapping, Sequence
from pyqi import export
from .registry import SENTINEL_FUNCTION_REGISTRY
from ._sentinel import (
    is_sentinel_value_dict, is_reserved_kwarg, 
    SentinelKey, SentinelValueDict, 
)

def resolve_field_value(value: Any, /, ): #  -> Any
    """ 
    - *`@note`* (special cases) `if is_sentinel_value(value) and sentinel in [MULTIPLE_SELECTION, RADIO_BUTTON_SELECT]` then just returns `value` 
    e.g. for MULTIPLE_SELECTION, caller is expected to be responsible for handling multiple values.
        - e.g. dynamic k-v entry generation (if applicable)
        - or maybe list becomes a delimited string to use SAPGUI copy from clipboard function 
    """
    if (value is None 
        or isinstance(value, Sequence) # handle in use location
    ): 
        return value
    if (isinstance(value, str)):
        sentinel = SentinelKey.try_resolve(value)
        return (
            value if sentinel is None 
            else SENTINEL_FUNCTION_REGISTRY.call(sentinel)
        )
    elif (is_sentinel_value_dict(value)):
        return (
            value if (value['sentinel'] in (
                SentinelKey.MULTIPLE_SELECTION.value, 
                SentinelKey.RADIO_BUTTON_SELECT.value
            )) 
            else resolve_sentinel_value_dict(value)
        )
    return value


def resolve_sentinel_value_dict(value: SentinelValueDict, /):
    sentinel = SentinelKey.resolve(value['sentinel'])
    if (not SENTINEL_FUNCTION_REGISTRY.is_registered(sentinel)):
        raise ValueError(f"No registered function exists for SentinelKey '{sentinel}'")
    args = value.get('args', [])
    kwargs: dict[str, Any] = {
        k: (
            resolve_sentinel_value_dict(v) if is_sentinel_value_dict(v) 
            else _resolve_kwarg_value(v)
        ) for k, v in value.items() 
        if not is_reserved_kwarg(k)
    }
    return SENTINEL_FUNCTION_REGISTRY.call(sentinel, *args, **kwargs)

def _resolve_kwarg_value(v: Any, /) -> Any:
    if (isinstance(v, str)):
        _result = SentinelKey.try_resolve(v)
        if _result is not None: return _result
    return v


def resolve_field_dict(fields: Mapping[str, Any], /) -> dict[str, Any]:
    return {
        k: resolve_field_value(v)
        for k, v in fields.items()
    }

__all__ = export(resolve_field_value, resolve_sentinel_value_dict, resolve_field_dict)