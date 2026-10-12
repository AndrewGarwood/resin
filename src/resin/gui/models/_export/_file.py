"""
*`@file`* `gui/models/_export/_file`
"""
from datetime import date
from pathlib import Path
from dataclasses import dataclass
from typing import (Any, Self, TypedDict, Optional, Literal)
from pyqi import (Json, export, dt, fs, require)
from lute import LogMsg

class FileOptionsDict(TypedDict, total=False):
    outdir: str
    filename: str
    outpath: str
    ref_date: str | Literal['none', 'today']
    how_apply_ref: str | Literal['auto']

@dataclass
class FileOptions(Json.Serial[FileOptionsDict]):
    """
    *`@extends`* `Json.Serial[FileOptionsDict]`
    ```
    - @property def outpath(self) -> Path: ...
    - @property def outdir(self) -> Path: ...
    - @property def filename(self) -> str: ...
    - @property def ref_date(self) -> Optional[date]: ...
    ```
    """
    _path: Path
    _ref_date: Optional[date] = None
    def __init__(
        self,
        outpath: Optional[fs.StrPath]=None,    
        outdir: Optional[fs.StrPath]=None,    
        filename: Optional[str]=None,
        ref_date: dt.DateValue | Literal['none', 'today'] | None = None,
        how_apply_ref: fs.RenameOperation | Literal['auto'] = fs.RenameOperation.REPLACE
    ):
        if (outpath and (outdir or filename)):
            raise ValueError(LogMsg(
                "Unsupported FileOptions argument(s)",
                "Expected: 1. outpath or 2. outdir and filename",
                "Received:",
                outpath=str(outpath),
                outdir=str(outdir),
                filename=str(filename)
            ))
        ref: date | None = (
            None if (ref_date is None or ref_date == 'none') 
            else dt.today() if ref_date == 'today' 
            else dt.resolve_date(ref_date)
        )
        path: Path | None = None
        if (outpath):
            path = fs.to_path(outpath)
        elif (outdir):
            path = fs.to_path(outdir).joinpath(filename or 'export.xlsx')
        else:
            raise RuntimeError(LogMsg(
                "Invalid arguments for FileOptions constructor",
                "Received:",
                outpath=str(outpath),
                outdir=str(outdir),
                filename=str(filename)
            ))
        if (ref is not None):
            path = path.with_name(fs.dated_filename(
                path.stem, 
                ext=path.suffix, 
                ref=ref,
                how=how_apply_ref
            ))
        self._ref_date = ref
        self._path = path
    
    @property
    def path(self) -> Path:
        return self._path
    @path.setter
    def path(self, other: fs.StrPath, /):
        self._path = fs.to_path(other)
    
    @property
    def dir(self) -> Path:
        return self._path.parent
    @dir.setter
    def dir(self, other: fs.StrPath, /):
        self._path = fs.to_path(other).joinpath(self._path.name)
    
    @property
    def name(self) -> str:
        return self._path.name
    @name.setter
    def name(self, other: str, /):
        self._path = self._path.with_name(
            require.non_empty_string(other, "FileOptions.name")
        )

    @property
    def ref_date(self) -> date | None: 
        return self._ref_date
    @ref_date.setter
    def ref_date(self, other: date | None, /):
        self._ref_date = other

    @classmethod
    def from_dict(cls, data: FileOptionsDict | dict[str, Any]) -> Self:
        try:
            _how = data.get('how_apply_ref')
            if (_how and _how != 'auto'): 
                _how = fs.RenameOperation.resolve(_how)
            return cls(
                outpath=data.get("outpath"),
                outdir=data.get("outdir"),
                filename=data.get("filename"),
                ref_date=data.get("ref_date"),
                how_apply_ref=(_how or 'auto')
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                received=Json.serialize(data)
            )) from e

    def to_dict(self) -> Json.JsonDict[FileOptionsDict]:
        return {
            "ref_date": (
                self._ref_date.isoformat() if self._ref_date is not None 
                else 'none'
            ),
            "outpath": str(self.path),
            "filename": self.name,
            "outdir": str(self.dir)
        }

    def exists(self):
        """ *`@returns`* `self.outpath.is_file()`"""
        return self.path.is_file()


__all__ = export(FileOptionsDict, FileOptions)

