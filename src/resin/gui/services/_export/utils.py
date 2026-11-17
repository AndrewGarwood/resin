"""
*`@files`* `gui/services/_export/utils`
"""
import time
from typing import Callable
from pyqi import Array, export
from pywinauto import Application
from resin.utils.winauto import (
    dump_class, 
    DesktopBackend, 
    wait_for_class, 
    WindowClass, 
    AutomationError, 
    is_owned_by
)

from resin.gui.models import (ExportOptions, LayoutSelector)
from resin.gui.components import (GridView)
from resin.gui.core.session import (Session)
from resin.gui.utils import (gui_id as GUI, wait_for_component)
from resin.gui.exceptions import SapGuiError
from .types import (NativeSaveDialogOptions)

import warnings
from lute import (LogMsg, get_logger)
mlog = get_logger(__file__)

def resolve_native_save_options(
    save_options: NativeSaveDialogOptions 
        | Callable[..., NativeSaveDialogOptions] 
        | None = None, 
    /,
) -> NativeSaveDialogOptions:
    return (
            NativeSaveDialogOptions() if save_options is None
            else save_options if isinstance(save_options, NativeSaveDialogOptions) 
            else save_options()
        )



def select_export_menu_item(
    grid: GridView,
    options: ExportOptions,
    /
) -> None:
    item_codes = Array.filter(
        [options.invoke.menu_item_id, *GUI.EXPORT_MENU_ITEMS], 
        None
    )
    errors: list[LogMsg] = []
    for code in item_codes:
        try:
            grid.select_context_menu_item(code)
            return
        except Exception as e:
            errors.append(LogMsg.err(e, menu_item_code=code))

    if (options.invoke.menu_item_position):
        try:
            grid.select_context_menu_item_by_position(
                options.invoke.menu_item_position
            )
            return
        except Exception as e:
            errors.append(LogMsg.err(
                e, 
                menu_item_position=options.invoke.menu_item_position
            ))
    raise SapGuiError(LogMsg(
        f"Failed to select export menu item. Attempts:",
        *Array.map(errors, str)
    ))


def handle_layout_selection(session: Session, layout: LayoutSelector, /): 
    if (not layout):
        return None
    try:
        if (layout.btn_id):
            session.press_button(layout.btn_id)
        elif (layout.vkey is not None):
            session.active_window.send_vkey(layout.vkey)
        else: # should never reach here if ExportOptions is valid... b/c throws if missing both btn_id and vkey
            raise ValueError(LogMsg(
                "Invalid ExportOptions.layout (LayoutSelector)", 
                "(missing both btn_id and vkey)"
            ))
        grid = wait_for_component(
            session, 
            layout.grid_id, 
            timeout=10.0,
            component_cls=GridView, 
            _raise=True
        )
        grid.select_row_by_value(
            GUI.SELECT_LAYOUT_GRID_NAME_COLUMN, 
            layout.name, 
            iter_reverse=layout.iter_reverse
        )
        return None
    except SapGuiError:
        raise
    except Exception as e:
        raise SapGuiError(LogMsg.err(
            e, 
            "Failed to select layout", 
            layout=str(layout)
        )) from e


def attempt_row_count(
    session: Session, 
    options: ExportOptions,
    /
) -> int | None:
    try:
        if (not options.invoke.grid_id):
            return None
        grid = session.find(options.invoke.grid_id, component_cls=GridView, _raise=False)
        if (grid is None):
            mlog.warning(LogMsg(
                f"Component not found, unable to obtain row_count from ExportOptions.invoke.grid_id",
                grid_id=options.invoke.grid_id
            ))
            return None
        return grid.row_count
    except Exception:
        return None


def open_grid_context_menu_pywinauto(
    main_wnd_handle: int,
    grid_handle: int,
    *, 
    timeout: float=2.0,
    backend: DesktopBackend | str = DesktopBackend.WIN32,
    menu_class: WindowClass | str = WindowClass.POPUP 
) -> None:
    
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", 
            message="32-bit application should be automated using 32-bit Python.*",
            category=UserWarning,
            module="pywinauto.application"
        )
        app = Application(backend=str(backend)).connect(handle=main_wnd_handle)
        wnd = app.window(handle=main_wnd_handle)
        grid = app.window(handle=grid_handle)
        wnd.set_focus()
        grid.set_focus()
        rect = grid.rectangle()
        x = rect.left + 10
        y = rect.top + 100
        grid.click_input(button="right", coords=(x - rect.left, y - rect.top))
        time.sleep(0.5)
        menu = wait_for_class(
            backend=backend, 
            class_name=menu_class, 
            visible_only=True,
            timeout=timeout
        )
        if (menu is None):
            dump_class(backend=backend, class_name=menu_class, visible_only=True)
            raise AutomationError(LogMsg(
                f"Failed to open context menu from GridView",
            )) 





__all__ = export(handle_layout_selection, select_export_menu_item, attempt_row_count)