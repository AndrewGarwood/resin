"""
*`@file`* `gui/services/transaction/multi_selection`
"""
from typing import Any, Callable
from pyqi import export
from resin.utils import (default_copy_to_clipboard)
from resin.gui.components.control import Tab, TextField
from resin.gui.components.table_control import TableControl
from resin.gui.components.window import FrameWindow
from resin.gui.core import Session
from resin.gui.exceptions import SapGuiError
from resin.gui.utils import gui_id as GUI
from resin.gui.utils.concurrency import wait_for_session_idle
from resin.models._field import MultiSelection, SentinelKey, ValueOptions
from .field_operation import _SetMultiSelection


def is_multi_selection_value(value: Any, /) -> bool:
    return (
        isinstance(value, (list, tuple, ValueOptions))
        or (isinstance(value, str) and value == SentinelKey.MULTIPLE_SELECTION)
        or (isinstance(value, dict) and (
            'include' in value or 'exclude' in value
            or value.get('sentinel') == SentinelKey.MULTIPLE_SELECTION
        ))
    )


def _selection_text(value: Any, /) -> str:
    if not isinstance(value, (str, int, float, bool)) or str(value) == "":
        raise ValueError("Multi-selection entries must be non-empty scalar values")
    return str(value)


def _selection_entries(
    selection: MultiSelection | None,
) -> tuple[
    tuple[str, ...], 
    tuple[tuple[str, str], ...]
]:
    if selection is None:
        return (), ()
    return (
        tuple(_selection_text(v) for v in selection.values),
        tuple(
            (_selection_text(r.lower), _selection_text(r.upper))
            for r in selection.ranges
        ),
    )


def prepare_multi_selection(
    field_id: str, 
    value: Any, 
    /, 
    *, 
    resolve: bool = True
) -> _SetMultiSelection:
    stem = GUI.SapFieldIdStem.parse(field_id)
    if (stem.component_type not in ('txt', 'ctxt')
        or not stem.base
        or stem.grid_x is not None
        or stem.container_index is not None
    ):
        raise ValueError("Multi-selection requires a non-indexed txt/ctxt selection field")
    button_stem = GUI.SapFieldIdStem.selection_button(stem.base)
    button_id = (
        GUI.join(GUI.parent(field_id), button_stem)
        if '/' in field_id else button_stem
    )
    if isinstance(value, ValueOptions):
        options = value
    elif isinstance(value, (list, tuple)):
        options = ValueOptions.from_sequence(value, resolve=resolve)
    elif isinstance(value, dict):
        definition = dict(value)
        if 'sentinel' in definition:
            if definition.pop('sentinel') != SentinelKey.MULTIPLE_SELECTION:
                raise ValueError("Expected a MULTIPLE_SELECTION action")
        options = ValueOptions.from_dict(definition, resolve=resolve)
    else:
        raise ValueError(
            "MULTIPLE_SELECTION requires include/exclude definitions or a list"
        )
    include_values, include_ranges = _selection_entries(options.include)
    exclude_values, exclude_ranges = _selection_entries(options.exclude)
    return _SetMultiSelection(
        field_id, 
        button_id,
        include_values, 
        include_ranges, 
        exclude_values, 
        exclude_ranges,
    )


def _write_rows(
    session: Session,
    window_id: str,
    tab_id: GUI.ComboTextFieldTabId,
    field_ids: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    copy_to_clipboard: Callable[[str], None] | None = default_copy_to_clipboard
) -> None:
    _table_id = GUI.parent(field_ids[0])
    table = session.wait_for_component(
        _table_id, 
        component_cls=TableControl, 
        _raise=True
    )
    wait_for_session_idle(session)
    if (copy_to_clipboard is not None
        and tab_id in GUI.ComboTextFieldTabId.single_value_tab_ids()
        ):
        values = [r[0] for r in rows]
        _payload = "\n".join(values)
        copy_to_clipboard(_payload)
        session.active_window.send_vkey(GUI.VKey.SHIFT_F12)
        wait_for_session_idle(session)
        # session.active_window.send_vkey(GUI.VKey.F8)
        return None
    
    table.scroll_to(0)
    for row_index, row in enumerate(rows):
        first = table.first_visible_row
        visible = table.visible_row_count
        if not first <= row_index < first + visible:
            # Commit the current page so SAP can grow the editable table.
            session.wait_for_component(
                window_id, 
                component_cls=FrameWindow, 
                _raise=True
            ).send_vkey(GUI.VKey.ENTER)
            wait_for_session_idle(session)
            if session.active_window.id != window_id:
                raise SapGuiError("Unexpected window while committing multi-selection rows")
            table.scroll_to(row_index)
            wait_for_session_idle(session)
            first = table.first_visible_row
            visible = table.visible_row_count
        if not first <= row_index < first + visible:
            raise SapGuiError(f"Table {_table_id!r} cannot reveal row {row_index}")
        for column, (field_id, value) in enumerate(zip(field_ids, row, strict=True), start=1):
            session.set_field_value(
                f"{field_id}[{column},{row_index - first}]",
                value, field_cls=TextField,
            )


def apply_multi_selection(
    session: Session, 
    operation: _SetMultiSelection, 
    /,
    copy_to_clipboard: Callable[[str], None] | None = default_copy_to_clipboard
) -> None:
    """Replace all four selections in the standard SAPLALDB dialog."""
    original_window = session.active_window.id
    original_index = GUI.get_window_index(original_window.rsplit('/', 1)[-1])
    if original_index is None:
        raise SapGuiError(f"Cannot determine active window index: {original_window!r}")
    expected_window = GUI.wnd(original_index + 1)
    session.press_button(operation.button_id)
    wait_for_session_idle(session)
    dialog = session.wait_for_component(
        expected_window, 
        component_cls=FrameWindow, 
        _raise=True
    )
    if session.active_window.id != dialog.id:
        raise SapGuiError("Multiple-selection dialog is not the active window")
    window_id = dialog.id
    window_index = original_index + 1
    groups = (
        (
            GUI.ComboTextFieldTabId.INCLUDE_SINGLE_VALUE,
            (
                GUI.ctxt_single_value_field_id(
                    window_index, 
                    GUI.ComboTextFieldTabId.INCLUDE_SINGLE_VALUE,
                    GUI.ComboTextFieldTabIndex.INCLUDE_SINGLE_VALUE,
                ),
            ), 
            tuple((v,) for v in operation.include_values)
        ),
        (
            GUI.ComboTextFieldTabId.INCLUDE_INTERVAL,
            tuple(
                GUI.ctxt_interval_field_id(
                    window_index, 
                    GUI.ComboTextFieldTabId.INCLUDE_INTERVAL,
                    GUI.ComboTextFieldTabIndex.INCLUDE_INTERVAL, 
                    endpoint,
                ) 
                for endpoint in ("LOW", "HIGH")
            ), 
            operation.include_ranges
        ),
        (
            GUI.ComboTextFieldTabId.EXCLUDE_SINGLE_VALUE,
            (
                GUI.ctxt_single_value_field_id(
                    window_index, 
                    GUI.ComboTextFieldTabId.EXCLUDE_SINGLE_VALUE,
                    GUI.ComboTextFieldTabIndex.EXCLUDE_SINGLE_VALUE, 
                    True,
                ),
            ), 
            tuple((v,) for v in operation.exclude_values)
        ),
        (
            GUI.ComboTextFieldTabId.EXCLUDE_INTERVAL,
            tuple(
                GUI.ctxt_interval_field_id(
                    window_index, 
                    GUI.ComboTextFieldTabId.EXCLUDE_INTERVAL,
                    GUI.ComboTextFieldTabIndex.EXCLUDE_INTERVAL, 
                    endpoint, 
                    True,
                ) 
                for endpoint in ("LOW", "HIGH")
            ), 
            operation.exclude_ranges
        ),
    )
    # Verify the standard dialog before using its destructive Delete All button.
    initial_tab = GUI.join(
        window_id, 
        GUI.usr(None), 
        GUI.TAB_STRIP, 
        GUI.tabp(GUI.ComboTextFieldTabId.INCLUDE_SINGLE_VALUE.value)
    )
    session.wait_for_component(
        initial_tab, 
        component_cls=Tab, 
        _raise=True
    ).select()
    session.wait_for_component(
        GUI.parent(groups[0][1][0]), 
        component_cls=TableControl, 
        _raise=True
    )
    wait_for_session_idle(session)
    if session.active_window.id != window_id:
        raise SapGuiError("Unexpected window while verifying multi-selection dialog")
    
    session.press_button(GUI.join(window_id, GUI.tbar(None, 0), GUI.btn(16))) 
    wait_for_session_idle(session)
    if session.active_window.id != window_id:
        raise SapGuiError("Unexpected window after clearing multi-selection")
    for tab_id, field_ids, rows in groups:
        if not rows:
            continue
        tab_path = GUI.join(
            window_id, 
            GUI.usr(None), 
            GUI.TAB_STRIP, 
            GUI.tabp(tab_id)
        )
        session.wait_for_component(
            tab_path, 
            component_cls=Tab, 
            _raise=True
        ).select()
        wait_for_session_idle(session)
        if session.active_window.id != window_id:
            raise SapGuiError("Unexpected window while selecting multi-selection tab")
        _write_rows(
            session, 
            window_id, 
            tab_id, 
            field_ids, 
            rows, 
            copy_to_clipboard=copy_to_clipboard
        )
    session.press_button(GUI.join(window_id, GUI.tbar(None, 0), GUI.btn(8)))
    wait_for_session_idle(session)
    if session.active_window.id != original_window:
        raise SapGuiError("Multiple-selection dialog did not return to its original window")

__all__ = export(
    is_multi_selection_value, 
    prepare_multi_selection, 
    apply_multi_selection
)