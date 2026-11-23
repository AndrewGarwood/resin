"""
*`@file`* `gui/services/_export/_shortcut.py`
"""
import time
from typing import (Callable)
from pyqi import (require, fs)
from pyqi.models._result import Result
from resin.gui.exceptions import SapGuiError
from resin.gui.models import (ExportMethod, ExportOptions)
from resin.gui.core import Session
from resin.gui.models._export.result import ExportDetails
from .registry import (EXPORT_METHOD_REGISTRY)
from .watcher import (native_save_dialog_watcher, NativeSaveDialogOptions)
from .locks import EXPORT_UI_LM
from .utils import (
    resolve_native_save_options, 
    attempt_row_count
)
from .dialog import (handle_export_dialog, _retain_scripting_session)


@EXPORT_METHOD_REGISTRY.register(ExportMethod.KEYBOARD_SHORTCUT)
def via_keyboard_shortcut(
    session: Session, 
    options: ExportOptions,
    save_dialog_options: NativeSaveDialogOptions 
        | Callable[..., NativeSaveDialogOptions] 
        | None = None
) -> Result[ExportDetails]:
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
        with EXPORT_UI_LM.engage_lock(), _retain_scripting_session(session):
            wnd = session.main_window
            if (not wnd.is_vkey_allowed(vkey)):
                raise SapGuiError(f"{vkey=} is not allowed in current state")
            wnd_handle = wnd.handle
            with native_save_dialog_watcher(
                save_options, 
                options.file.path, 
                owner_hwnd=wnd_handle
            ) as watcher:
                time.sleep(0.25)
                wnd.send_vkey(vkey)
                handle_export_dialog(session, options, watcher)
        return Result.ok(
            via_keyboard_shortcut,
            data=ExportDetails(
                fs.wait_for_file_exists(options.file.path), 
                row_count=attempt_row_count(session, options)
            ),
            message=options.success_message()
        )
    except Exception as e:
        return Result.fail(
            via_keyboard_shortcut, 
            error=e, 
            message=options.failure_message(),
            status=session.get_status()
        )



__all__ = ["via_keyboard_shortcut"]