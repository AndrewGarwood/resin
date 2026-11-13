"""
*`@file`* `_workbook/utils`
"""
import re
from pyqi import (export, dt, guard, require)
from lute import (LogMsg, annotate)
from .exceptions import ConfigurationError

_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")

def is_excel_error_value(value: object, /) -> bool:
    return (
        not isinstance(value, bool) # isinstance(True, int) → True
        and isinstance(value, int) 
        and -2146827000 < value < -2146826000
    )

def parse_refresh_timestamp(
    value: object,
    /,
    *,
    require_null_tzinfo: bool = True,
    use_1904_epoch: bool=False
) -> dt.datetime | None:
    """
    *`@note`* if `value` is `float | int` or a `float` derived from `str`, interprets the number to be the number 
    of days since `EXCEL_EPOCH or EXCEL_1904_EPOCH`
    """
    if (value is None or value == ""):
        return None
    if (isinstance(value, dt.datetime)):
        if value.tzinfo is not None and require_null_tzinfo:
            raise ConfigurationError(LogMsg(
                "Expected an unzoned workbook refresh timestamp",
                require_null_tzinfo=require_null_tzinfo,
                tzinfo=str(value.tzinfo),
                value=annotate(value)
            ))
        return value

    if (isinstance(value, str)):
        literal = value.strip()
        if literal.startswith("="):
            literal = literal[1:].strip()
        if literal.startswith('"') and literal.endswith('"'):
            literal = literal[1:-1]
        if not _NUMBER.fullmatch(literal):
            raise ConfigurationError(LogMsg(
                "Invalid workbook refresh timestamp literal",
                "Expected literal (cleaned value) to match number regex pattern",
                value=annotate(value),
                literal=annotate(literal)
            ))
        value = float(literal)
    if (not guard.is_number(value)):
        raise ConfigurationError(LogMsg.bad_arg(
            value,
            f"{parse_refresh_timestamp.__name__}(<value>, ...)",
            "Expected value to be Excel serial timestamp",
            float, int
        ))
    serial = require.non_negative_number(
        value, 
        f"{parse_refresh_timestamp.__name__}(<value>, ...)",
    )
    if serial == 0: 
        return None
    return dt.datetime_from.days_since_xl_epoch(serial, use_1904_epoch=use_1904_epoch)



__all__ = export(
    is_excel_error_value, 
    parse_refresh_timestamp
)