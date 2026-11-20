"""
*`@file`* `ibp/_options`
"""
from copy import deepcopy
from pathlib import Path
from typing import (TypedDict, Any, Self, Required)
from pyqi import (Json, require, export, fs)
from lute import LogMsg
from noxl import (CellAddress, CellAddressLike)
from .constants import (DEFAULT_SHEETNAME, DEFAULT_DATA_ORIGIN)


class WorkbookOptionsDict(TypedDict, total=False):
    path: Required[str]
    sheetname: str
    data_origin: CellAddressLike
    required_headers: list[str]
    description: str

class WorkbookOptions(Json.Serial[WorkbookOptionsDict]):
    """
    *`@extends`* `Json.Serial[WorkbookOptionsDict]`
    """
    path: Path
    sheetname: str = DEFAULT_SHEETNAME
    _data_origin: CellAddressLike | None
    required_headers: list[str]
    description: str | None

    def __init__(
        self,
        path: fs.StrPath,
        sheetname: str | None = None,
        data_origin: CellAddressLike | None = None,
        required_headers: list[str] | None = None,
        description: str | None = None
    ):
        self.path = fs.to_path(path)
        self.sheetname = sheetname or DEFAULT_SHEETNAME
        self._data_origin = data_origin or DEFAULT_DATA_ORIGIN
        self.required_headers = required_headers or []
        self.description = description

    @classmethod
    def from_dict(cls, data: WorkbookOptionsDict | dict[str, Any], /) -> Self:
        try:
            return cls(
                path=require.non_empty_string(data['path']),
                sheetname=data.get('sheetname'),
                data_origin=data.get('data_origin'),
                required_headers=data.get('required_headers'),
                description=data.get('description')
            )
        except (ValueError, KeyError): raise
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e,
                f"Failed to construct ibp.WorkbookOptions from dictionary",
                received=Json.serialize(data)
            )) from e

    @property
    def pathstem(self):
        return self.path.stem

    @property
    def data_origin(self) -> CellAddress:
        if (not self._data_origin):
            raise RuntimeError(LogMsg(f"self._data_origin is undefined"))
        return CellAddress.from_any(self._data_origin)
    @data_origin.setter
    def data_origin(self, value: CellAddressLike, /):
        self._data_origin = value

    @property
    def header_origin(self):
        return self.data_origin.offset(rows=-1)
    @property
    def info_addr(self):
        return self.header_origin.offset(rows=-1)

    def with_path(
        self, 
        path: fs.StrPath, 
        /, 
        sheetname: str | None=None
    ):
        return WorkbookOptions(
            path=fs.to_path(path), 
            sheetname=sheetname or self.sheetname,
            data_origin=self._data_origin,
            required_headers=deepcopy(self.required_headers),
            description=self.description
        )


__all__ = export(WorkbookOptionsDict, WorkbookOptions)