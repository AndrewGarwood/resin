"""
*`@file`* `gui/models/_export/dialog`
"""
from typing import (TypedDict, Any)
from pyqi import (Json, export)
from lute import LogMsg
from ...utils import gui_id as GUI

class SaveDialogDict(TypedDict, total=False):
    dirpath_field_id: str
    filename_field_id: str
    confirm_button_id: str

class SaveDialog(Json.Serial[SaveDialogDict]):
    """
    ```
    dirpath_field_id: str  # default: gui_id.export_dialog_dirpath()
    filename_field_id: str # default: gui_id.export_dialog_filename()
    confirm_button_id: str # default: gui_id.export_dialog_confirm_btn()
    ```
    """
    dirpath_field_id: str
    filename_field_id: str
    confirm_button_id: str
    def __init__(
        self,
        dirpath_field_id: str | None = None,
        filename_field_id: str | None = None,
        confirm_button_id: str | None = None
    ):
        self.dirpath_field_id = dirpath_field_id or GUI.export_dialog_dirpath()
        self.filename_field_id = filename_field_id or GUI.export_dialog_filename()
        self.confirm_button_id = confirm_button_id or GUI.export_dialog_confirm_btn()
    @classmethod
    def from_dict(cls, data: SaveDialogDict | dict[str, Any],/):
        try:
            return cls() if not data else cls(
                dirpath_field_id=data.get("dirpath_field_id"),
                filename_field_id=data.get("filename_field_id"),
                confirm_button_id=data.get("confirm_button_id")
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, received=Json.serialize(data)
            )) from e

    def to_dict(self) -> SaveDialogDict | dict[str, Any]:
        return {
            "dirpath_field_id": self.dirpath_field_id,
            "filename_field_id": self.filename_field_id,
            "confirm_button_id": self.confirm_button_id
        }


__all__ = export(SaveDialogDict, SaveDialog)