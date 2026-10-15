"""
*`@file`* `gui/services/_export/_toolbar`
"""
from __future__ import annotations
import time
from typing import (Callable)
from pyqi import (require, fs, Result)
from resin.gui.components.window import MainWindow
from resin.gui.models import (ExportMethod, ExportOptions)
from resin.gui.core import Session
from resin.gui.models._export.result import ExportDetails
from resin.gui.utils import (gui_id as GUI)
from .registry import (EXPORT_METHOD_REGISTRY)
from .watcher import (native_save_dialog_watcher, NativeSaveDialogOptions)
from .locks import EXPORT_UI_LM
from .utils import (attempt_row_count, resolve_native_save_options)
from .dialog import (handle_export_dialog)



@EXPORT_METHOD_REGISTRY.register(ExportMethod.TOOLBAR_BUTTON)
def via_toolbar(
    session: Session, 
    options: ExportOptions,
    save_dialog_options: NativeSaveDialogOptions 
        | Callable[..., NativeSaveDialogOptions] 
        | None = None
) -> Result[ExportDetails]: 
    try:
        if (options.method.value != ExportMethod.TOOLBAR_BUTTON.value):
            raise ValueError(
                f"Invalid ExportOptions.method value for function {via_toolbar.__name__}")
        btn_id = require.non_empty_string(options.invoke.export_button_id)
        save_options = resolve_native_save_options(save_dialog_options)
        with EXPORT_UI_LM.engage_lock():
            wnd = session.find(
                GUI.wnd(GUI.MAIN_WINDOW_INDEX), 
                component_cls=MainWindow, 
                _raise=True
            )
            wnd_handle = wnd.handle
            with native_save_dialog_watcher(
                save_options, 
                options.file.path, 
                owner_hwnd=wnd_handle
            ) as watcher:
                time.sleep(0.25)
                session.press_button(btn_id)
                handle_export_dialog(session, options, watcher)
        saved = fs.wait_for_file_exists(options.file.path)
        return Result.ok(
            via_toolbar,
            data=ExportDetails(
                saved, 
                row_count=attempt_row_count(session, options)
            ),
            message=options.success_message()
        )
    except Exception as e:
        return Result.fail(
            via_toolbar, 
            error=e, 
            message=options.success_message()
        )