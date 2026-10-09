"""
*`@file`* `gui/services/_export/types`
"""
from __future__ import annotations

from dataclasses import dataclass, field as _field
from typing import (Any, Callable, Iterable, Sequence, TypeAlias, TypedDict)
from pyqi import (export)
from pyqi.models import (RetryOptions)
from resin.utils.winauto import (DesktopBackend, 
    ControlOptions, CommonControl
)
from .constants import (
    DEFAULT_OVERWRITE_CONFIRM_BUTTON_OPTIONS, 
    DEFAULT_OVERWRITE_DIALOG_OPTIONS, 
    DEFAULT_SAVE_BUTTON_OPTIONS,
    DEFAULT_SAVE_DIALOG_OPTIONS,
    DEFAULT_SAVE_EDIT_OPTIONS,
    default_dialog_selector
)




DialogControl: TypeAlias = Any

@dataclass
class NativeSaveDialogOptions:
    save_dialog: ControlOptions = _field(default=DEFAULT_SAVE_DIALOG_OPTIONS)
    save_edit_selector: Callable[[Iterable[Any]], Any] = _field(default=default_dialog_selector)
    save_edit: ControlOptions = _field(default=DEFAULT_SAVE_EDIT_OPTIONS)
    save_btn: ControlOptions = _field(default=DEFAULT_SAVE_BUTTON_OPTIONS)
    overwrite_dialog: ControlOptions = _field(default=DEFAULT_OVERWRITE_DIALOG_OPTIONS)
    overwrite_btn: ControlOptions = _field(default=DEFAULT_OVERWRITE_CONFIRM_BUTTON_OPTIONS)
    retry: RetryOptions = _field(default_factory=RetryOptions)
    backend: DesktopBackend = DesktopBackend.WIN32


__all__ = export("DialogControl", NativeSaveDialogOptions)