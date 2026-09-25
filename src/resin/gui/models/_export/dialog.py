"""
*`@file`* `gui/models/_export/dialog`
"""

from datetime import date
from pathlib import Path
from dataclasses import dataclass, replace
from typing import (TypedDict, Required, NotRequired, Any, Optional, Mapping, TypeAlias, Literal)
from pyqi import (String, Json, export, Result, dt, fs)
from lute import LogMsg




class SaveDialogDict(TypedDict, total=False):
    dirpath_field_id: str
    filename_field_id: str
    confirm_button_id: str

class SaveDialog(Json.Serial[SaveDialogDict]):
    _dirpath_field_id: str
    _filename_field_id: str
    _confirm_button_id: str
