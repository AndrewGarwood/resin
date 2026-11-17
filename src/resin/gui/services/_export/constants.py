"""
*`@file`* `gui/services/_export/constants`
"""
from typing import Iterable
from resin.utils.winauto import (
    ControlOptions, WindowClass, CommonControl
)
from pywinauto.base_wrapper import (BaseWrapper)

NATIVE_SAVE_DIALOG_TIMEOUT = 300.0
NATIVE_SAVE_DIALOG_POLL = 0.25

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
DEFAULT_SAVE_DIALOG_OPTIONS = ControlOptions(
    class_name=WindowClass.DIALOG,
    title_re=SAVE_DIALOG_TITLE_PATTERN
)

DEFAULT_SAVE_EDIT_OPTIONS = ControlOptions(
    class_name=CommonControl.EDIT
)
DEFAULT_SAVE_BUTTON_OPTIONS = ControlOptions(
    class_name=CommonControl.BUTTON,
    title_re=SAVE_BUTTON_PATTERNS
)
DEFAULT_OVERWRITE_DIALOG_OPTIONS = ControlOptions(
    class_name=WindowClass.DIALOG,
    title_re=OVERWRITE_DIALOG_TITLE_PATTERNS
)
DEFAULT_OVERWRITE_CONFIRM_BUTTON_OPTIONS = ControlOptions(
    class_name=CommonControl.BUTTON,
    title=OVERWRITE_CONFIRM_BUTTON_TITLES
)


def default_dialog_selector(candidates: Iterable[BaseWrapper], /,) -> BaseWrapper:
    return max(candidates, key=lambda c: c.rectangle().width())