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



def resolve_field_value(value: Any, /, ):
    """ 
    *`@note`* `if is_sentinel_value(value) and sentinel == MULTIPLE_SELECTION` then just returns `value` 
    because expects caller to be responsible for handling multiple values.
        - e.g. dynamic k-v entry generation (if applicable)
        - or maybe list becomes a delimited string to use SAPGUI copy from clipboard function 
    """
    if (isinstance(value, str)):
        try:
            sentinel = SentinelKey.resolve(value)
            return SENTINEL_FUNCTION_REGISTRY.call(sentinel)
        except ValueError:
            return value
    if (isinstance(value, Sequence)): # handle in use location
        return value
    if (is_sentinel_value_dict(value)):
        if (not SentinelKey.can_resolve(value['sentinel'])):
            raise ValueError(f"Unsupported SentinelKey '{value['sentinel']}'")
        if (value.get("sentinel") == SentinelKey.MULTIPLE_SELECTION.value):
            return value
        return resolve_sentinel_value_dict(value)
    return value


def resolve_sentinel_value_dict(value: SentinelValueDict, /):
    sentinel = SentinelKey.resolve(value['sentinel'])
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
        if (SentinelKey.can_resolve(v)):
            return SENTINEL_FUNCTION_REGISTRY.call(SentinelKey.resolve(v))
    return v


def resolve_field_dict(fields: Mapping[str, Any], /) -> dict[str, Any]:
    return {
        k: resolve_field_value(v)
        for k, v in fields.items()
    }

__all__ = export(resolve_field_value, resolve_sentinel_value_dict, resolve_field_dict)