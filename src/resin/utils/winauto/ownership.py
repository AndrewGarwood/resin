"""
*`@file`* `resin/utils/winauto/ownership`
"""
from __future__ import annotations
import win32con, win32gui, win32process
from pyqi import export

def iter_owner_chain(hwnd: int):
    """Yield a window followed by each native owner in its owner chain."""
    current = hwnd

    while current:
        yield current
        current = win32gui.GetWindow(current, win32con.GW_OWNER)


def is_owned_by(hwnd: int, expected_owner_hwnd: int) -> bool:
    """
    Return True when expected_owner_hwnd occurs anywhere in hwnd's
    native owner chain.
    """
    return expected_owner_hwnd in iter_owner_chain(hwnd)

def window_process_id(hwnd: int) -> int:
    _, process_id = win32process.GetWindowThreadProcessId(hwnd)
    return process_id

def is_candidate_dialog(
    hwnd: int,
    *,
    expected_owner_hwnd: int | None,
    expected_process_id: int | None,
) -> bool:
    if expected_owner_hwnd is not None and not is_owned_by(
        hwnd,
        expected_owner_hwnd,
    ):
        return False

    if (
        expected_process_id is not None
        and window_process_id(hwnd) != expected_process_id
    ):
        return False

    return True

__all__ = export(iter_owner_chain, is_owned_by, window_process_id)