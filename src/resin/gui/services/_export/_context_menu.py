"""
*`@file`* `gui/services/_export/_context_menu`
"""
import time
from typing import (Callable)
from pyqi import (require, fs)
from pyqi.models._result import Result
from resin.gui.components.control import Button
from resin.gui.components.grid_view import GridView
from resin.gui.models import (ExportMethod, ExportOptions)
from resin.gui.core import Session
from resin.gui.models._export.result import ExportDetails
from resin.gui.utils import (wait_for_component, gui_id as GUI)
from resin.utils.winauto import (Win32Window)
from .registry import (EXPORT_METHOD_REGISTRY)
from .watcher import (native_save_dialog_watcher, NativeSaveDialogOptions)
from .locks import EXPORT_UI_LM
from .utils import (open_grid_context_menu_pywinauto, resolve_native_save_options)
from .dialog import (handle_export_dialog)
from .constants import (NATIVE_SAVE_DIALOG_TIMEOUT, NATIVE_SAVE_DIALOG_POLL)

# TODO: try invoking context menu without pywinauto by selecting a cell first;

@EXPORT_METHOD_REGISTRY.register(ExportMethod.CONTEXT_MENU)
def via_context_menu(
    session: Session, 
    options: ExportOptions,
    save_dialog_options: NativeSaveDialogOptions 
        | Callable[..., NativeSaveDialogOptions] 
        | None = None
) -> Result[ExportDetails]:
    try:
        if (str(options.method) != ExportMethod.CONTEXT_MENU.value):
            raise ValueError(
                f"Invalid ExportOptions.method value for function {via_context_menu.__name__}"
            )
        _grid_id = require.non_empty_string(
            options.invoke.grid_id, 
            f"ExportOptions<{ExportMethod.CONTEXT_MENU.value}>.invoke.grid_id"
        )
        save_options = resolve_native_save_options(save_dialog_options)
        grid = session.wait_for_component(
            _grid_id, 
            component_cls=GridView, 
            _raise=True, 
            timeout=3.0
        )
        grid_handle = grid.handle
        row_count = grid.row_count
        with EXPORT_UI_LM.engage_lock():
            wnd = session.main_window
            wnd_handle = wnd.handle
            with native_save_dialog_watcher(
                save_options,
                options.file.path, 
                owner_hwnd=wnd_handle,
            ) as watcher:
                menu_item_id = options.invoke.menu_item_id or GUI.EXCEL_EXPORT_FUNCTION_CODE
                open_grid_context_menu_pywinauto(
                    main_wnd_handle=wnd_handle, 
                    grid_handle=grid_handle, 
                    backend=save_options.backend,
                    menu_class=options.invoke.menu_element_class or Win32Window.POPUP
                )
                time.sleep(0.5)
                grid.select_context_menu_item(menu_item_id)
                session.press_button(options.save.confirm_button_id)
                # confirm_btn = wait_for_component(
                #     session, 
                #     options.save.confirm_button_id, 
                #     component_cls=Button, 
                #     _raise=True
                # )
                # confirm_btn.press()
                handle_export_dialog(session, options, watcher)
        return Result.ok(
            via_context_menu,
            data=ExportDetails(
                fs.wait_for_file_exists(options.file.path), 
                row_count
            ),
            message=options.success_message()
        )
    except Exception as e:
        return Result.fail(
            via_context_menu, 
            error=e, 
            message=options.failure_message()
        )