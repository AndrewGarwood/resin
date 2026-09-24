"""
*`@file`* `gui/components/grid_view`
- [Sap GuiGridView](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/4af24c3281fb4d6a809e53238562d3b2.html)
"""
from __future__ import annotations
from typing import (Any, Optional)
from .shell import (Shell)
from ..utils.concurrency import (busy_safe)
from .registry import register_component
from pyqi import export
from lute import LogMsg

@register_component()
class GridView(Shell):
    @busy_safe()
    def context_menu(self) -> GridView:
        """ 
        Calling contextMenu emulates the context menu request. 
        
        GridView extends Shell → can call
            - SelectContextMenuItem
            - SelectContextMenuItemByPosition
            - SelectContextMenuItemByText
        """
        self._com.ContextMenu()
        return self

    @busy_safe()
    def select_export_as_excel(self):
        EXCEL_EXPORT_FUNCTION_CODE = "&XXL"
        self.select_context_menu_item(EXCEL_EXPORT_FUNCTION_CODE)
        return self

    @busy_safe()
    def press_toolbar_button(self, button_id: str) -> GridView:
        self._com.PressToolbarButton(button_id)
        return self

    @busy_safe()
    def press_toolbar_context_button(self, button_id: str):
        """ `'&MB_EXPORT'` """
        self._com.PressToolbarContextButton(button_id)
        return self
    
    def press_enter(self):
        self._com.PressEnter()
        return self
    
    def clear_selection(self):
        self._com.ClearSelection()
        return self
    
    def click(self, row: int, col: str):
        self._com.Click(row, col)
        return self
    
    def double_click(self, row: int, col: str):
        self._com.DoubleClick(row, col)
        return self

    @property
    def row_count(self) -> int:
        return self._gateway.get_property(
            self._com, 
            "RowCount", 
            int, 
            _raise=True
        )
    
    @property
    def title(self) -> str:
        return self._gateway.get_property(self._com, "Title", str, _raise=True)
    
    @property
    def column_order(self) -> Any:
        return self._gateway.get_property(self._com, "ColumnOrder", _raise=True)

    def _get_cell_value(self, row: int, column: str, /, ignore_case: bool=True) -> str:
        cell_value = str(self._com.GetCellValue(row, column))
        return cell_value.casefold() if ignore_case else cell_value
    
    def select_row(self, row: int, column: str):
        self._com.SetCurrentCell(row, column)
        self._com.ClickCurrentCell()
        return None
    
    def find_row(
        self, 
        column: str, 
        value: str, 
        *, 
        ignore_case: bool = True,
        iter_reverse: bool = False, 
        # need to check if rows are ordered by create date or alphabetically
    ) -> Optional[int]:
        target = str(value).casefold() if ignore_case else str(value)
        if iter_reverse:
            for row in range(self._com.RowCount, 0, -1):
                if self._get_cell_value(row, column, ignore_case) == target:
                    return row
        else: 
            for row in range(self._com.RowCount):
                if self._get_cell_value(row, column, ignore_case) == target:
                    return row
        return None

    def find_rows(self, column: str, value: str, *, ignore_case: bool=True) -> list[int]:
        target = str(value).casefold() if ignore_case else str(value)
        matches: list[int] = []
        for row in range(self._com.RowCount):
            if self._get_cell_value(row, column, ignore_case) == target:
                matches.append(row)
        return matches
    
    def select_row_by_value(self, column: str, value: str, *, ignore_case: bool=True):
        """ searches for and clicks row. GridView might close in sapgui, so return none... """
        row = self.find_row(column, value, ignore_case=ignore_case)
        if row is None:
            raise ValueError(LogMsg(
                f"No row found with {column} == {value}"
            ))
        self.select_row(row, column)


__all__ = export(GridView)