"""
*`@file`* `gui/services/_export/constants`
"""
from resin.utils.winauto import (DesktopBackend, 
    Win32Window, ControlOptions, AutomationError, WindowClass, CommonControl
)

SAVE_BUTTON_PATTERNS = [
    r"^.*Save.*$",
    r"^&Save$",
    r"^Save$",
    r"^&Open$",
    r"^Open$",
    r"^OK$",
]

SAVE_DIALOG_TITLE_PATTERN = r".*(Save As|Save|Export).*"

OVERWRITE_DIALOG_TITLE_PATTERNS = [
    r".*Confirm Save As.*",
    r".*Save As.*",
    r".*already exists.*",
    r".*Confirm.*",
]

OVERWRITE_CONFIRM_BUTTON_TITLES = [
    "Yes", "&Yes", "Replace", "&Replace", "OK"
]

