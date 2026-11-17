"""
*`@file`* `utils/_clipboard`
- not using pyperclip for now.
"""
import sys, subprocess
from lute import LogMsg

_PLATFORM_TO_CLIPBOARD_CMD = {
    "win32": "clip",
    "darwin": "pbcopy"
}

SUPPORTED_PLATFORMS = frozenset(_PLATFORM_TO_CLIPBOARD_CMD.keys())

def default_copy_to_clipboard(payload: str, /) -> None:
    _platform = sys.platform
    if _platform not in SUPPORTED_PLATFORMS:
        raise NotImplementedError(LogMsg(
            f"Platform (Operating System) not supported",
            platform=_platform,
            SUPPORTED_PLATFORMS=list(SUPPORTED_PLATFORMS)
        ))
    cmd = _PLATFORM_TO_CLIPBOARD_CMD[_platform]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
    proc.communicate(payload.strip())

__all__ = ["default_copy_to_clipboard", "SUPPORTED_PLATFORMS"]