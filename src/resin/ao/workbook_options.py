"""
*`@file`* `ao/workbook_options`
"""
from pathlib import Path
from typing import (Any, Callable, Iterable, Mapping, TypedDict, Required, Self)
from pyqi import (Json, fs, io, SpreadsheetFileExt, require, export)
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
    whether the workbook prompts/params should be re-entered when refreshing 
    (e.g. if using dynamic value)
    """
    
    def __init__(
        self,
        path: fs.StrPath,
        id: str | None = None,
        ds_alias: str | None=None,
        columns: list[str] | None = None,
        set_prompts: bool = False
    ):
        self.path = fs.to_path(path)
        self._id = id
        self.ds_alias = require.non_empty_string(
            ds_alias or DEFAULT_AO_DATASOURCE, 
            'ao.WorkbookOptions.ds_alias'
        )
        self._columns = columns
        self.set_prompts = set_prompts

    @classmethod
    def from_dict(cls, data: WorkbookOptionsDict | dict[str, Any], /) -> Self:
        try:
            return cls(
                path=fs.to_path(data['path']),
                id=data.get('id'),
                ds_alias=data.get('ds_alias'),
                columns=data.get('columns'),
                set_prompts=data.get('set_prompts', False)
            )
        except (ValueError, KeyError): raise
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                f"Failed to construct ao.WorkbookOptions from dictionary",
                received=Json.serialize(data)
            ))


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

    def detect_columns_from_template(
        self, 
        src: Path, 
        *, 
        sheetname: str | Callable[[str], bool]='Sheet1', 
        sep: str | None = None
    ) -> list[str]:
        """
        #### TODO: move to resin/_workbook/...
        because SAP AO workbook sheets can have columns with no header/name, 
        one option is to store the complete header in a file. 
        - not that robust. 
        - e.g. could instead try to dynamically generate the missing header values. 
        but keepin it simple for now.
        """
        if (not src.is_file()):
            raise ValueError(LogMsg(f"src Path must be an existing file"))
        try:
            ext = src.suffix.lower()
            if ext in SpreadsheetFileExt.excel_extensions():
                return list(find_header(src,sheetname=sheetname).headers)
            for x in [SpreadsheetFileExt.CSV, SpreadsheetFileExt.TSV]:
                if ext == x.value: return io.read_list(src, sep=x.separator)
            return io.read_list(src, sep=sep)
        except Exception as e:
            raise RuntimeError(LogMsg.err(e, 
                f"Unable to obtain column list",
                src=str(src),
                sep=sep
            )) from e

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

__all__ = export(WorkbookOptions, WorkbookOptionsDict)