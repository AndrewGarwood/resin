"""
*`@files`* `gui/services/_export/dialog`
- after ExportOptions.invoke, handles sapgui save dialog 
or windowsnative save dialog
"""
from __future__ import annotations
from collections.abc import Generator
from contextlib import contextmanager
import time
from pyqi import export
from resin.gui.models import (ExportOptions)
from resin.gui.components import (TextField)
from resin.gui.core.session import (Session)
from .watcher import (NativeSaveDialogWatcher)
from .constants import (NATIVE_SAVE_DIALOG_TIMEOUT)

from lute import (get_logger)
mlog = get_logger(__file__)

@contextmanager
def retain_scripting_session(session: Session) -> Generator[None, None, None]:
    """
    - SAP's dialog substitution depends on a live GuiSession reference, not
    just the application or a wrapper that re-resolves each COM operation.
    """
    dispatch = session.gateway.get_session(session.connection_id, session.id)
    try:
        yield
    finally:
        del dispatch

def _try_sapgui_dialog(session: Session, options: ExportOptions, /) -> bool:
    """
    *`@returns`* `handled (bool)` 
        - whether or not SAPGUI dialog was used to to export
        - `True`  → don't need to use watcher
        - `False` → wait to see if watcher encounters and handles 
        native save dialog
    """
    dirpath_field = session.wait_for_component(
        options.save.dirpath_field_id, 
        component_cls=TextField, 
        _raise=False, 
        timeout=3.0
    )
    if (dirpath_field is not None):
        dirpath_field.set(str(options.file.dir))
        session.set_field_value(
            options.save.filename_field_id, 
            options.file.name, 
            field_cls=TextField
        )
        session.press_button(options.save.confirm_button_id)
        return True
    return False


def handle_export_dialog(
    session: Session,
    options: ExportOptions,
    watcher: NativeSaveDialogWatcher,
    /,
    *,
    timeout: float = NATIVE_SAVE_DIALOG_TIMEOUT,
) -> None:
    deadline = time.monotonic() + timeout
    if watcher.wait_handled(timeout=min(5.0, timeout)):
        return
    if watcher.error is not None:
        raise RuntimeError(
            "Native save dialog watcher terminated unexpectedly"
        ) from watcher.error

    if _try_sapgui_dialog(session, options):
        return
    remaining = max(0.0, deadline - time.monotonic())
    if watcher.wait_handled(timeout=remaining):
        return
    if watcher.error is not None:
        raise RuntimeError(
            "Native save dialog watcher failed"
        ) from watcher.error
    raise TimeoutError(
        f"No export dialog was handled within {timeout:.1f} seconds"
    )

__all__ = export(handle_export_dialog, retain_scripting_session)