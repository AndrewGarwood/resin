"""
*`@files`* `gui/services/_export/dialog`
- after ExportOptions.invoke, handles sapgui save dialog 
or windowsnative save dialog
"""

from pyqi import export
from resin.gui.components.control import Button
from resin.gui.models import (ExportOptions)
from resin.gui.components import (TextField)
from resin.gui.core.session import (Session)
from resin.gui.utils import (wait_for_component)

from .watcher import (NativeSaveDialogWatcher)

from lute import (LogMsg, get_logger)
mlog = get_logger(__file__)

def _try_sapgui_dialog(session: Session, options: ExportOptions, /) -> bool:
    """
    *`@returns`* `handled (bool)` 
        - whether or not SAPGUI dialog was used to to export
        - `True`  → don't need to use watcher
        - `False` → wait to see if watcher encounters and handles 
        native save dialog
    """
    dirpath_field = wait_for_component(
        session, 
        options.save.dirpath_field_id, 
        component_cls=TextField, 
        _raise=False, 
        timeout=3.0
    )
    if (dirpath_field is not None):
        dirpath_field.set(str(options.file.dir))
        wait_for_component(
            session, 
            options.save.filename_field_id, 
            component_cls=TextField, 
            _raise=True, 
            timeout=3.0
        ).set(options.file.name)
        wait_for_component(
            session, 
            options.save.confirm_button_id,
            component_cls=Button,
            _raise=True,
            timeout=3.0
        ).press()
        return True
    return False



def handle_export_dialog(
    session: Session, 
    options: ExportOptions, 
    watcher: NativeSaveDialogWatcher, 
    /,
) -> None:
    handled = _try_native_dialog(options, watcher, timeout=10.0)
    if (handled): 
        return None
    handled = _try_sapgui_dialog(session, options)
    if (handled):
        mlog.debug(f"Handled SAPGUI export dialog")
        return None
    mlog.debug(LogMsg(f"SAPGUI dialog not detected, waiting for watcher. . ."))
    handled = _try_native_dialog(options, watcher, timeout=30.0)
    if (not handled):
        raise TimeoutError(LogMsg(
            f"Watcher timeout exceeded, no export dialog handled"
        ))
    return None


def _try_native_dialog(
    options: ExportOptions, 
    watcher: NativeSaveDialogWatcher, 
    /,
    timeout:float = 30.0
) -> bool:
    if (watcher.wait_handled(timeout=timeout)):
        mlog.debug(f"Native save dialog handled by watcher within {timeout=}s")
        return True
    if (options.file.exists()):
        mlog.debug(f"outpath already exists; treating as completed")
        watcher.mark_handled()
        return True
    return False


__all__ = export(_try_sapgui_dialog, handle_export_dialog)