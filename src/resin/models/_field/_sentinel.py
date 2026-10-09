"""
*`@file`* `models/_field/_sentinel`
"""
from pyqi.models import BaseStrEnum
from pyqi.utils import export
from typing import (Any, Literal, Mapping, TypeGuard, TypedDict, NotRequired)


SENTINEL_KWARG = "sentinel"
ARGS_KWARG = "args"
RESERVED_KWARGS = set([SENTINEL_KWARG, ARGS_KWARG])

def is_reserved_kwarg(value: Any, /) -> TypeGuard[Literal["sentinel", "args"]]:
    return isinstance(value, str) and value in RESERVED_KWARGS


class SentinelKey(BaseStrEnum):
    FIRST_DAY_OF_MONTH = "FIRST_DAY_OF_MONTH"
    LAST_DAY_OF_MONTH = "LAST_DAY_OF_MONTH"
    CUSTOM_DATE = "CUSTOM_DATE" # COMPUTE_DATE
    CUSTOM_RANGE = "CUSTOM_RANGE"
    FIRST_DAY_OF_YEAR = "FIRST_DAY_OF_YEAR"
    LAST_DAY_OF_YEAR = "LAST_DAY_OF_YEAR"
    ROLLING_YEAR_LOWER = "ROLLING_YEAR_LOWER"
    """  last day of current month last year"""
    ROLLING_YEAR_UPPER = "ROLLING_YEAR_UPPER"
    """ last day of current month this year"""
    ROLLING_12M_LOWER = "ROLLING_12M_LOWER"
    ROLLING_12M_UPPER = "ROLLING_12M_UPPER"
    CURRENT_DAY = "CURRENT_DAY"
    RADIO_BUTTON_SELECT = "RADIO_BUTTON_SELECT"
    PREVIOUS_BUSINESS_DAY = "PREVIOUS_BUSINESS_DAY"

class SentinelValue(TypedDict):
    sentinel: SentinelKey | str
    args: NotRequired[list[Any]]

def is_sentinel_value(value: Any, /) -> TypeGuard[SentinelValue]:
    return (
        isinstance(value, Mapping) 
        and SENTINEL_KWARG in value
        and isinstance(value[SENTINEL_KWARG], str)
    )



__all__ = export(
    SentinelKey, SentinelValue, 
    is_reserved_kwarg,
    is_sentinel_value, "SENTINEL_KWARG", "ARGS_KWARG", 
)