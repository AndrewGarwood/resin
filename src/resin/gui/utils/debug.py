"""
*`@file`* `resin/gui/utils/debug`
"""
from pathlib import Path
from typing import (Any)
import lute
from json import dumps as json_dumps
LogMsg = lute.LogMsg
mlog = lute.get_logger(Path(__file__).parent.parent)




def debug_component(
    obj: Any, 
    /, 
    print_to_console: bool=False,
    attrs: list[str]=[
        "Id",
        "Name",
        "Type",
        "Text",
        "Changeable",
        "Enabled",
        "Visible",
        "ContainerType",
    ]
) -> dict[str, object]:
    props = {}
    for name in attrs:
        try:
            props[name] = getattr(obj, name)
        except Exception as e:
            props[name] = f"<unavailable: {e}>"
    if (print_to_console):
        mlog.debug(json_dumps(props, indent=4))
    return props
