"""
*`@file`* `models/_field/register_sentinels`
"""
from collections.abc import Collection
from datetime import date
from typing import (Any, Optional)
from pyqi import (dt, Array)
from pyqi._dt import (FormatString, compute_date)
from ._sentinel import (SentinelKey)
from re import search as re_search
from lute import LogMsg
from .registry import (SENTINEL_FUNCTION_REGISTRY)


@SENTINEL_FUNCTION_REGISTRY.register(SentinelKey.CURRENT_DAY)
def current_day(fmt: str=FormatString.MDY_SLASH.value) -> str: 
    return compute_date().strftime(fmt)


@SENTINEL_FUNCTION_REGISTRY.register(SentinelKey.FIRST_DAY_OF_MONTH)
def first_day_of_month_text(
    anchor: str | date | None = None, 
    fmt: str | FormatString = FormatString.MDY_SLASH.value
) -> str:
    if isinstance(anchor, str): anchor = dt.Date.strptime(anchor, fmt)
    return compute_date(anchor=anchor, day="first").strftime(fmt)


@SENTINEL_FUNCTION_REGISTRY.register(SentinelKey.LAST_DAY_OF_MONTH)
def last_day_of_month_text(
    anchor: str | date | None = None, 
    fmt: str | FormatString = FormatString.MDY_SLASH.value
) -> str:
    if isinstance(anchor, str): anchor = dt.Date.strptime(anchor, fmt)
    return compute_date(anchor=anchor, day="last").strftime(fmt)


@SENTINEL_FUNCTION_REGISTRY.register(SentinelKey.FIRST_DAY_OF_YEAR)
def first_day_of_year_text(
    year: int | None = None,  
    fmt: str | FormatString = FormatString.MDY_SLASH.value
) -> str:
    y = year or date.today().year
    return date(y, 1, 1).strftime(fmt)


@SENTINEL_FUNCTION_REGISTRY.register(SentinelKey.LAST_DAY_OF_YEAR)
def last_day_of_year_text(
    year: int | None = None,  
    fmt: str | FormatString = FormatString.MDY_SLASH.value
) -> str:
    y = year or date.today().year
    return date(y, 12, 31).strftime(fmt)


@SENTINEL_FUNCTION_REGISTRY.register(SentinelKey.ROLLING_YEAR_LOWER)
def rolling_year_lower_text(
    fmt: str | FormatString = FormatString.MDY_SLASH.value
    ) -> str:
    return compute_date(year_offset=-1, day="last").strftime(fmt)


@SENTINEL_FUNCTION_REGISTRY.register(SentinelKey.ROLLING_YEAR_UPPER)
def rolling_year_upper_text(
    fmt: str | FormatString = FormatString.MDY_SLASH.value
) -> str:
    return compute_date(year_offset=0, day="last").strftime(fmt)


@SENTINEL_FUNCTION_REGISTRY.register(SentinelKey.ROLLING_12M_LOWER)
def rolling_12m_lower(
    fmt: str | FormatString = FormatString.MDY_SLASH.value
) -> str:
    return compute_date(year_offset=-1, day="first").strftime(fmt)


@SENTINEL_FUNCTION_REGISTRY.register(SentinelKey.ROLLING_12M_UPPER)
def rolling_12m_upper(
    fmt: str | FormatString = FormatString.MDY_SLASH.value
) -> str:
    return compute_date(day="last").strftime(fmt)

@SENTINEL_FUNCTION_REGISTRY.register(SentinelKey.CUSTOM_DATE)
def custom_date(
    *,
    fmt: str | FormatString = FormatString.MDY_SLASH.value, 
    **kwargs
) -> str:
    """
    e.g. LAST_DAY_OF_PREV_MONTH
    {
        "sentinel": "COMPUTE_DATE",
        "month_offset": -1,
        "day": "last",
    }
    """
    return compute_date(**kwargs).strftime(fmt)

@SENTINEL_FUNCTION_REGISTRY.register(SentinelKey.PREVIOUS_BUSINESS_DAY)
def previous_business_day(
    fmt: str | FormatString = FormatString.MDY_SLASH.value,
    holidays: Optional[Collection[str]] = None
) -> str:
    _holidays = Array.filter_map(list(holidays or []), dt.Date.resolve)
    return dt.Date.previous_business_day(None, holidays=_holidays).strftime(fmt)

@SENTINEL_FUNCTION_REGISTRY.register(SentinelKey.CUSTOM_RANGE)
def custom_range(
    *,
    lower: dict[str, Any],
    upper: dict[str, Any],
    leftpad: int=2,
    fmt: str | FormatString = FormatString.MY_SLASH.value,
): 
    m = re_search(r"(?P<sep>[^%\da-zA-Z])", fmt)
    if not m:
        raise ValueError(LogMsg(
            f"Invalid date format provided",
            f"format must have separator",
            f"format={fmt}"
        ))
    sep = m.groupdict()["sep"]
    lb = compute_date(**lower).strftime(fmt)
    lb_split = lb.split(sep, 1)
    lb_left = lb_split[0]
    lb_right = lb_split[1]
    while len(lb_left) < leftpad:
        lb_left = "0" + lb_left
    left = f"{lb_left}{sep}{lb_right}"

    ub = compute_date(**upper).strftime(fmt)
    ub_split = ub.split(sep, 1)
    ub_left = ub_split[0]
    ub_right = ub_split[1]
    while len(ub_left) < leftpad:
        ub_left = "0" + ub_left
    right = f"{ub_left}{sep}{ub_right}"
    return f"{left} - {right}"