"""
*`@file`* `models/_field/_resolve`
"""
from copy import deepcopy
from typing import Any, Mapping
from pyqi import export
from lute import LogMsg
from .registry import SENTINEL_FUNCTION_REGISTRY
from ._sentinel import (
    is_reserved_kwarg,
    SentinelKey, SentinelValueDict,
)

_ACTION_SENTINELS = frozenset({
    SentinelKey.RADIO_BUTTON_SELECT,
    SentinelKey.MULTIPLE_SELECTION,
})


def resolve_field_value(value: Any, /) -> Any:
    """Resolve a field definition without modifying it.

    Bare sentinel strings are supported for fields and list entries. 
    ~~Strings inside provider arguments or ordinary dictionaries remain literal~~; 
    - **recommended** to use an explicit sentinel object for nested expressions. GUI actions are preserved.
    """
    return _resolve_value(value, path="value", allow_bare_sentinel=True)


def resolve_sentinel_value_dict(value: SentinelValueDict, /, allow_bare_sentinel: bool = True) -> Any:
    if not isinstance(value, Mapping) or 'sentinel' not in value:
        raise ValueError("value: expected a sentinel object")
    return _resolve_value(value, path="value", allow_bare_sentinel=allow_bare_sentinel)


def _call_provider(
    sentinel: SentinelKey,
    args: list[Any],
    kwargs: dict[str, Any],
    *,
    path: str,
) -> Any:
    if not SENTINEL_FUNCTION_REGISTRY.is_registered(sentinel):
        raise ValueError(f"{path}: no registered function for sentinel {sentinel.value!r}")
    try:
        return SENTINEL_FUNCTION_REGISTRY.call(sentinel, *args, **kwargs)
    except Exception as e:
        raise ValueError(LogMsg.err(e, f"{path}: failed to resolve sentinel {sentinel.value!r}")) from e


def _resolve_value(value: Any, *, path: str, allow_bare_sentinel: bool) -> Any:
    if isinstance(value, Mapping):
        if 'sentinel' in value:
            key = value['sentinel']
            if not isinstance(key, str):
                raise TypeError(f"{path}.sentinel: expected a string")
            sentinel = SentinelKey.try_resolve(key)
            if sentinel is None:
                raise ValueError(f"{path}.sentinel: unknown sentinel {key!r}")
            if sentinel in _ACTION_SENTINELS:
                return deepcopy(dict(value))
            args = value.get('args', [])
            if not isinstance(args, list):
                raise TypeError(f"{path}.args: expected a list")
            if not all(isinstance(k, str) for k in value):
                raise TypeError(f"{path}: provider keyword names must be strings")
            resolved_args = [
                _resolve_value(v, path=f"{path}.args[{i}]", allow_bare_sentinel=allow_bare_sentinel)
                for i, v in enumerate(args)
            ]
            kwargs = {
                k: _resolve_value(v, path=f"{path}.{k}", allow_bare_sentinel=allow_bare_sentinel)
                for k, v in value.items()
                if not is_reserved_kwarg(k)
            }
            return _call_provider(sentinel, resolved_args, kwargs, path=path)
        return {
            k: _resolve_value(v, path=f"{path}[{k!r}]", allow_bare_sentinel=allow_bare_sentinel)
            for k, v in value.items()
        }
    if isinstance(value, str):
        sentinel = SentinelKey.try_resolve(value) if allow_bare_sentinel else None
        if sentinel is None or sentinel in _ACTION_SENTINELS:
            return value
        return _call_provider(sentinel, [], {}, path=path)
    if isinstance(value, (list, tuple)):
        items = [
            _resolve_value(
                v, path=f"{path}[{i}]", allow_bare_sentinel=allow_bare_sentinel
            )
            for i, v in enumerate(value)
        ]
        return tuple(items) if isinstance(value, tuple) else items
    return value


def resolve_field_dict(fields: Mapping[str, Any], /) -> dict[str, Any]:
    return {
        k: _resolve_value(v, path=f"fields[{k!r}]", allow_bare_sentinel=True)
        for k, v in fields.items()
    }

__all__ = export(resolve_field_value, resolve_sentinel_value_dict, resolve_field_dict)