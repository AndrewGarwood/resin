"""
*`@file`* `gui/components/table_control`
"""
from .container import VContainer
from .registry import register_component
from ..exceptions import SapComError


@register_component()
class TableControl(VContainer):
    """
    SAP table control; re-resolve its dispatch after every scrollbar change.
    - [GuiTableControl](https://help.sap.com/docs/sap_gui_for_windows/b47d018c3b9b45e897faf66a6c0885a8/ce1d9e64355d49568e5def5271aea2db.html?version=770.08)
    """

    @property
    def visible_row_count(self) -> int:
        count = self.gateway.get_property(
            self._resolve(), "VisibleRowCount", int, _raise=True
        ) 
        if count <= 0:
            raise SapComError(f"Table {self.id!r} has no visible rows")
        return count

    @property
    def first_visible_row(self) -> int:
        scrollbar = self.gateway.get_property(
            self._resolve(), "VerticalScrollbar", _raise=True
        )
        position = self.gateway.get_property(scrollbar, "Position", int, _raise=True)
        if position < 0:
            raise SapComError(f"Table {self.id!r} has an invalid scrollbar position")
        return position

    def scroll_to(self, row: int, /) -> None:
        if not isinstance(row, int) or isinstance(row, bool) or row < 0:
            raise ValueError("Table scroll row must be a non-negative integer")
        try:
            scrollbar = self.gateway.get_property(
                self._resolve(), "VerticalScrollbar", _raise=True
            )
            scrollbar.Position = row
        except Exception as e:
            raise SapComError(f"Unable to scroll table {self.id!r} to row {row}") from e


__all__ = ["TableControl"]
