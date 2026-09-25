"""
*`@file`* `gui/models/_export/_file`
"""
from datetime import date
from pathlib import Path
from dataclasses import dataclass
from typing import (TypedDict, Optional, Literal)
from pyqi import (Json, export, dt, fs)
from lute import LogMsg

class FileOptionsDict(TypedDict, total=False):
    outdir: str
    filename: str
    outpath: str
    ref_date: str | Literal['none', 'today']

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
        ref_date: dt.DateValue | Literal['none', 'today']='today'
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
            None if ref_date == 'none' 
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
                ref=ref
            ))
        self._path = path
    
    @property
    def outpath(self) -> Path:
        return self._path
    @property
    def outdir(self) -> Path:
        return self._path.parent
    @property
    def filename(self) -> str:
        return self._path.name
    @property
    def ref_date(self): 
        return self._ref_date
    
    def to_dict(self) -> Json.JsonDict[FileOptionsDict]:
        return {
            "ref_date": (
                self._ref_date.isoformat() if self._ref_date is not None 
                else 'none'
            ),
            "outpath": str(self.outpath),
            "filename": self.filename,
            "outdir": str(self.outdir)
        }



__all__ = export(FileOptionsDict, FileOptions)

