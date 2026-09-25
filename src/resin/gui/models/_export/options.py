"""
*`@file`* `gui/models/_export/options`
"""
from datetime import date
from pathlib import Path
from dataclasses import dataclass, replace
from typing import (TypedDict, Required, NotRequired, Any, Optional, Mapping, TypeAlias, Literal)
from pyqi import (String, Json, export, Result, dt, fs)
from lute import LogMsg

from ._file import (FileOptions, FileOptionsDict)
from .layout import (LayoutSelector, LayoutSelectorDict)

class ExportMethod(String.BaseEnum):
    NONE = "none"
    """ → do not export the Transaction data"""
    CONTEXT_MENU = "context_menu"
    TOOLBAR_BUTTON = "toolbar_button"
    KEYBOARD_SHORTCUT = "keyboard_shortcut"
    """ e.g. `SendVKey(16)` """
    TOOLBAR_CONTEXT = "toolbar_context"
    """ ***not implemented/supported*** """
