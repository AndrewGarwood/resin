"""
*`@file`* `models/_field/registry`
"""
from typing import (Final, Any)
from pyqi import (Registry)
from ._sentinel import (SentinelKey)

SENTINEL_FUNCTION_REGISTRY: Final[
    Registry[SentinelKey, Any]
] = Registry(SentinelKey, normalize_key=SentinelKey.resolve)


__all__ = ["SENTINEL_FUNCTION_REGISTRY"]