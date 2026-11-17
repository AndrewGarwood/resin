"""
*`@file`* `utils/winauto/window/utils`
"""
from re import Pattern
from pyqi import require
from pywinauto import WindowSpecification, Desktop
from .options import WindowOptionsDict
from lute import LogMsg

def resolve_window_options_dict(
    value: int | str | Pattern[str] | WindowOptionsDict, 
    /,
) -> WindowOptionsDict:
    """
    does not yet check validity of entries if value is dict
    """
    if (not value):
        raise ValueError(LogMsg.bad_arg(
            value, 
            "resolve_window_options_dict(<value>)",
            "value must be non-empty",
            int, str, Pattern, WindowOptionsDict, 
            "non-empty str or non-empty WindowOptionsDict or positive integer"
        ))
    return (
        value if isinstance(value, (dict))
        else WindowOptionsDict(
            handle=require.positive_integer(
                value, 
                "resolve_window_options_dict(<value> as window handle (int))"
            )
        ) if isinstance(value, int)
        else WindowOptionsDict(title=value) if isinstance(value, str)
        else WindowOptionsDict(title_re=value.pattern)
    )


def resolve_window_specification(
    value: int | str | Pattern[str] | WindowOptionsDict | WindowSpecification,
    /,
    *,
    backend: str | None=None
) -> WindowSpecification:
    if (not value):
        raise ValueError(LogMsg.bad_arg(
            value, 
            "resolve_window_options_dict(<value>)",
            "value must be non-empty if is not WindowSpecification",
            str, 
            Pattern, 
            WindowOptionsDict, 
            WindowSpecification,
        ))

    if isinstance(value, WindowSpecification):
        return value
    return (
        Desktop(backend=backend)
        .window(
            **resolve_window_options_dict(value)
        )
    )

__all__ = [
    "resolve_window_specification", "resolve_window_options_dict",
]