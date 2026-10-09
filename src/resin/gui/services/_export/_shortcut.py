"""
*`@file`* `gui/services/_export/_shortcut.py`
"""
import time
from typing import (Callable)
from pyqi import (require, fs)
from resin.gui.components.window import MainWindow
from resin.gui.models import (ExportMethod, ExportResult, ExportOptions)
from resin.gui.core import Session
from resin.gui.models._export.result import ExportDetails
from resin.gui.utils import (gui_id as GUI)
from .registry import (EXPORT_METHOD_REGISTRY)
from .watcher import (native_save_dialog_watcher, NativeSaveDialogOptions)
from .locks import EXPORT_UI_LM
from .utils import (
    resolve_native_save_options, 
    attempt_row_count
)
from .dialog import (handle_export_dialog)


@EXPORT_METHOD_REGISTRY.register(ExportMethod.KEYBOARD_SHORTCUT)
def via_keyboard_shortcut(
    session: Session, 
    options: ExportOptions,
    save_dialog_options: NativeSaveDialogOptions 
        | Callable[..., NativeSaveDialogOptions] 
        | None = None
) -> ExportResult:
    try:
        if (str(options.method) != ExportMethod.KEYBOARD_SHORTCUT.value):
            raise ValueError(
                f"Invalid ExportOptions.method value for function {via_keyboard_shortcut.__name__}"
            )
        vkey = require.positive_integer(
            options.invoke.vkey, 
            name=f"ExportOptions<{ExportMethod.KEYBOARD_SHORTCUT.value}>.invoke.vkey"
        )
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
                wnd.send_vkey(vkey)
                handle_export_dialog(session, options, watcher)
        saved = fs.wait_for_file_exists(options.file.path)
        return ExportResult.ok(
            via_keyboard_shortcut,
            data=ExportDetails(
                saved, 
                row_count=attempt_row_count(session, options)
            ),
            message=options.success_message()
        )
    except Exception as e:
        return ExportResult.fail(
            via_keyboard_shortcut, 
            error=e, 
            message=options.failure_message()
        )