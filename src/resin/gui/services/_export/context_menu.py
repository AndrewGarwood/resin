"""
*`@file`* `gui/services/_export/context_menu`
"""

from pathlib import Path
import time
from typing import (Callable)
from pyqi import (require)
from resin.gui.components.grid_view import GridView
from resin.gui.components.window import MainWindow
from resin.gui.exceptions import SapGuiError
from .registry import (EXPORT_METHOD_REGISTRY)
from .watcher import (native_save_dialog_watcher, NativeDialogWatcher, NativeSaveDialogOptions)
from .locks import EXPORT_UI_LM
from resin.gui.models import (ExportMethod, ExportResult, ExportOptions)
from resin.gui.core import Session
from resin.gui.utils import (wait_for_component, gui_id as GUI)
from lute import LogMsg


@EXPORT_METHOD_REGISTRY.register(ExportMethod.CONTEXT_MENU)
def via_context_menu(
    session: Session, 
    options: ExportOptions,
    outpath: str | Path,
    save_dialog_options: NativeSaveDialogOptions | Callable[..., NativeSaveDialogOptions] | None = None
):
    try:
        save_options = (
            NativeSaveDialogOptions() if save_dialog_options is None
            else save_dialog_options if isinstance(save_dialog_options, NativeSaveDialogOptions) 
            else save_dialog_options()
        )
        _grid_id = require.non_empty_string(
            options.invoke.grid_id, 
            f"ExportOptions<{ExportMethod.CONTEXT_MENU}>.invoke.grid_id"
        )
        grid = wait_for_component(
            session, 
            _grid_id, 
            component_cls=GridView, 
            _raise=True, 
            timeout=10
        )
        row_count = grid.row_count
        with EXPORT_UI_LM.engage_lock():
            time.sleep(0.25)
            wnd = session.find(
                GUI.wnd(GUI.MAIN_WINDOW_INDEX), 
                component_cls=MainWindow, 
                _raise=True
            )
            with native_save_dialog_watcher(
                save_options, 
                outpath, 
                ownder_hwnd=wnd.handle 
            ) as watcher:
                ...
        pass
    except SapGuiError:
        raise
    except Exception as e:
        raise RuntimeError(LogMsg.err(
            e, 
            "Failed to export using ContextMenu"
        )) from e