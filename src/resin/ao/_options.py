"""
*`@file`* `ao/_options`
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import (Any, Iterable, Mapping, TypedDict, Required)
from pyqi import (Json, fs, io, SpreadsheetFileExt, require)
from noxl.engines.pyxl import find_header
from lute import LogMsg
from .constants import (DEFAULT_AO_DATASOURCE)


class WorkbookOptionsDict(TypedDict, total=False):
    id: str
    path: Required[str]
    ds_alias: str
    columns: list[str]
    prompts: Mapping[str, Any]
    set_prompts: bool

class WorkbookOptions(Json.Serial[WorkbookOptionsDict]):
    """
    *`@extends`* `Json.Serial[WorkbookOptionsDict]`
    """
    _id: str | None
    path: Path
    ds_alias: str
    prompts: Mapping[str, Any]
    """
    `query parameters` - SAP AO calls them `prompts`
    """
    _columns: list[str] | None
    set_prompts: bool = False
    """
    whether the workbook prompts/params should be re-entered when refreshing (e.g. if using dynamic value)
    """
    
    def __init__(
        self,
        path: fs.StrPath,
        id: str | None = None,
        ds_alias: str=DEFAULT_AO_DATASOURCE,
        columns: list[str] | None = None,
        set_prompts: bool = False
    ):
        self.path = fs.to_path(path)
        self._id = id
        self.ds_alias = ds_alias
        self._columns = columns
        self.set_prompts = set_prompts

    @property
    def pathstem(self):
        """ *`@returns`* `self.path.stem` """
        return self.path.stem

    @property
    def columns(self) -> list[str]:
        if not self._columns:
            raise RuntimeError(LogMsg(f"self._columns is undefined or empty"))
        return self._columns
    @columns.setter
    def columns(self, columns: Iterable[str], /) -> None:
        self._columns = list(columns)

    def detect_columns_from_template(self, src: Path, *, sep: str = "\t") -> str:
        """
        because SAP AO workbook sheets can have columns with no header
        """
        raise NotImplementedError



    @property
    def id(self) -> str:
        """
        *`@returns`* `self._id or WorkbookOptions.generate_id(self.path, self.ds_alias)`
        """
        return self._id or WorkbookOptions.generate_id(self.path, self.ds_alias)
    @id.setter
    def id(self, id: str, /) -> None:
        self._id = id

    @staticmethod
    def generate_id(path: fs.StrPath, ds_alias: str, /):
        """
        - *`@returns`* 
        `f"f({path.stem if isinstance(path, Path) else path})-d({ds_alias})"`
        - used as default `id` value for `ao.WorkbookOptions`
        """
        path_info = require.non_empty_string(
            path.stem if isinstance(path, Path) else path,
            "ao.WorkbookOptions.generate_id(<path>, ...)"
            )
        ds_alias = require.non_empty_string(
            ds_alias,
            "ao.WorkbookOptions.generate_id(..., <ds_alias>)"
            )
        return f"f({path_info})-d({ds_alias})"