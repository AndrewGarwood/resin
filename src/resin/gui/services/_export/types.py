"""
*`@file`* `gui/services/_export/types`
"""
from __future__ import annotations

from dataclasses import dataclass, field as _field
from typing import (Any, Callable, Iterable, TypeAlias, Sequence)
from pyqi import (export)
from pyqi.models import (RetryOptions)
from resin.utils.winauto import (
    DesktopBackend, 
    ControlOptions, 
)
from resin.utils.winauto.tools import get_backend_name
from .constants import (
    DEFAULT_OVERWRITE_CONFIRM_BUTTON_OPTIONS, 
    DEFAULT_OVERWRITE_DIALOG_OPTIONS, 
    DEFAULT_SAVE_BUTTON_OPTIONS,
    DEFAULT_SAVE_DIALOG_OPTIONS,
    DEFAULT_SAVE_EDIT_OPTIONS,
    default_dialog_selector
)


@dataclass
class NativeSaveDialogOptions:
    save_dialog: ControlOptions = _field(default=DEFAULT_SAVE_DIALOG_OPTIONS)
    save_edit_selector: Callable[[Iterable[Any]], Any] = _field(default=default_dialog_selector)
    save_edit: ControlOptions = _field(default=DEFAULT_SAVE_EDIT_OPTIONS)
    save_btn: ControlOptions = _field(default=DEFAULT_SAVE_BUTTON_OPTIONS)
    overwrite_dialog: ControlOptions = _field(default=DEFAULT_OVERWRITE_DIALOG_OPTIONS)
    overwrite_btn: ControlOptions = _field(default=DEFAULT_OVERWRITE_CONFIRM_BUTTON_OPTIONS)
    retry: RetryOptions = _field(default_factory=RetryOptions)
    backend: DesktopBackend | str | None = None


    def __post_init__(self):
        if (not self.backend):
            self.backend = get_backend_name()


__all__ = export(NativeSaveDialogOptions)


# def _find_filename_edit(dialog):
#     candidates = [
#         control
#         for control in (dialog if isinstance(dialog, Sequence) else dialog.descendants(class_name=CommonControl.EDIT.value))
#         if control_is_available(control)
#     ]
#     by_control_id = [
#         control
#         for control in candidates
#         if control.control_id() == 1148
#     ]

#     if len(by_control_id) == 1:
#         return by_control_id[0]

#     raise RuntimeError(
#         f"Unable to uniquely identify filename edit; "
#         f"found {len(candidates)} available Edit controls"
#     )
