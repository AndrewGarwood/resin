"""
*`@file`* `gui/utils/gui_id/parts`
"""
from __future__ import annotations
from typing import (Literal)
from pyqi import (export, require)
import re

def join(*parts: str) -> str:
    """ *`@returns`* `'/'.join(x.strip().rstrip("/") for x in parts)` """
    return '/'.join(x.strip().rstrip("/") for x in parts if (x))

def parent(id: str, /) -> str:
    return id.rsplit("/", 1)[0]

def stem(id: str, /) -> str:
    """ *`@returns`* `id.rsplit("/", 1)[-1]` """
    return id.rsplit("/", 1)[-1]

def replace_stem(id: str, new_stem: str, /) -> str:
    return join(parent(id), new_stem)

def replace_window(id: str, new_index: int, /) -> str:
    """
    - prepends `wnd[{new_index}]/` to `id` if `id` does not already contain `wnd[{old_index}]`
    - else replaces `old_index` with `new_index` 
    """
    index = require.non_negative_integer(new_index, f"window index")
    if ("wnd[" not in id):
        return join(f"wnd[{index}]", id)
    return re.sub(r"wnd\[\d+\]", f"wnd[{index}]", id)

def after_window(id: str, /) -> str:
    """ return string containing id parts after wnd[i]"""
    parts = id.split("/")
    N = len(parts)
    for i in range(N):
        part = parts[i]
        if part.startswith("wnd["):
            if i < N - 1:
                return "/".join(parts[i+1:N])
            return ""
    return ""


def get_container_index(id: str, /, container_type: str | Literal["wnd"]) -> int | None:
    """
    *`@returns`* `None` `if f"{container_type}[" not in item_id`
    - `else` tries to match `rf"{container_type}\\[(?P<index>\\d+)\\]"` → `int(index)`
    """
    if (f"{container_type}[" not in id):
        return None
        # raise ValueError(LogMsg(
        #     f"Unable to find container index",
        #     f"container_type is not subtring of item_id",
        #     item_id=item_id,
        #     container_type=container_type
        # ))
    pat = rf"{container_type}\[(?P<index>\d+)\]"
    m = re.match(pat, id)
    return int(m.groupdict()["index"]) if m else None

def get_window_index(id: str, /):
    return get_container_index(id, "wnd")

def field_type(field_id: str, /) -> str:
    """
    Extracts the SAP field type prefix from a field ID.
    - returns empty string if no match found
    
    Examples:
        `"wnd/.../radP_OPTD2"` -> `"rad"`
        `"wnd/.../ctxtS_VKORG-LOW"` -> `"ctxt"`
    """
    last = field_id.rsplit("/", 1)[-1]
    
    m = re.match(r"[a-z]+", last)
    return m.group(0) if m else ""


__all__ = export(
    join, 
    parent, 
    stem, 
    replace_stem, 
    get_container_index, 
    get_window_index, 
    field_type,
    replace_window
)
