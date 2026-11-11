"""
*`@file`* `ao/_options`
"""

from pathlib import Path
from dataclasses import dataclass
from typing import (Any, Callable, Iterable, Mapping, Self, TypedDict, Required)
from pyqi import (Json, fs, io, SpreadsheetFileExt, require, Array, export)
from noxl.engines.pyxl import find_header
from lute import LogMsg
from resin._workbook.base_controller_options import (
    BaseControllerOptions, BaseControllerOptionsDict
)
from resin._workbook.types import StagingPolicy
from .constants import (COM_ADD_IN_NAME, DEFAULT_AO_DATASOURCE)


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

    def detect_columns_from_template(
        self, 
        src: Path, 
        *, 
        sheetname: str | Callable[[str], bool]='Sheet1', 
        sep: str | None = None
    ) -> list[str]:
        """
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


# =============================================================================
# Unfortunately cannot have TypedDicts inherit from one another....
# So, kinda unoptimal usage/implementation here
# =============================================================================

class ControllerOptionsDict(TypedDict, total=False):
    """
    `(TypedDict, total=False)`
    ```
    # ==== BaseControllerOptionsDict ====
    staging: str
    staging_policy: str | StagingPolicy
    stage_roots: list[str]
    cooldown_seconds: float
    poll_seconds: float
    startup_timeout_seconds: float
    # ====================================
    # AO specific options
    addin_name: str
    default_ds_alias: str

    ```
    """
    staging: Required[str]
    staging_policy: str | StagingPolicy
    stage_roots: list[str]
    cooldown_seconds: float
    poll_seconds: float
    startup_timeout_seconds: float

    addin_name: str
    ds_alias: str


@dataclass
class ControllerOptions(BaseControllerOptions):
    addin_name: str = COM_ADD_IN_NAME
    ds_alias: str = DEFAULT_AO_DATASOURCE
    """ Default Datasource alias to use if `WorkbookOptions.ds_alias` is undefined """

    @classmethod
    def from_dict(
        cls, 
        data: (BaseControllerOptionsDict 
            | ControllerOptionsDict 
            | dict[str, Any]
        ), 
        /,
    ) -> Self:
        try:
            return cls(
                staging=fs.to_path(data['staging']),
                staging_policy = StagingPolicy.resolve(
                    data.get('staging_policy', StagingPolicy.ALWAYS)
                ),
                stage_roots=Array.map(
                    data.get('stage_roots', []), 
                    fs.to_path
                ),
                cooldown_seconds=require.positive_number(
                    data.get('cooldown_seconds', 3600)
                ),
                poll_seconds = require.positive_number(
                    data.get('poll_seconds', 0.25)
                ),
                startup_timeout_seconds = require.positive_number(
                    data.get('startup_timeout_seconds', 90)
                ),
                addin_name=require.non_empty_string(
                    data.get('addin_name', COM_ADD_IN_NAME)
                ),
                ds_alias=require.non_empty_string(
                    data.get('ds_alias', DEFAULT_AO_DATASOURCE)
                )
            )
        except (KeyError, ValueError): raise
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e,
                f"Failed to create ao.ControllerOptions instance",
                received=Json.serialize(data)
            )) from e

    def get_base_options(self) -> BaseControllerOptions:
        _base_keys = set(BaseControllerOptions.keys())
        return BaseControllerOptions(
            **{
                k: getattr(self, k)
                for k in self.keys() if k in _base_keys
            }
        )

__all__ = export(
    WorkbookOptions, 
    WorkbookOptionsDict, 
    ControllerOptionsDict, 
    ControllerOptions
)