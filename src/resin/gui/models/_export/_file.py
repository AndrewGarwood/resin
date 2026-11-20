"""
*`@file`* `gui/models/_export/_file`
"""
from datetime import date
from pathlib import Path
from dataclasses import dataclass
from typing import (Any, Self, TypedDict, Literal)
from pyqi import (Json, export, dt, fs, require)
from lute import LogMsg

class FileOptionsDict(TypedDict, total=False):
    outdir: str
    name: str
    path: str

# @dataclass
class FileOptions(Json.Serial[FileOptionsDict]):
    """
    *`@extends`* `Json.Serial[FileOptionsDict]`
    ```
    - @property def path(self) -> Path: ...
    - @property def outdir(self) -> Path: ...
    - @property def name(self) -> str: ...
    ```
    """
    _path: Path
    def __init__(
        self,
        path: fs.StrPath | None=None,    
        outdir: fs.StrPath | None=None,    
        name: str | None=None,
    ):
        if (path and not outdir and not name):
            path = fs.to_path(path)
        elif (outdir):
            path = fs.to_path(outdir).joinpath(name or f'export.xlsx')
        elif (path and outdir and name):
            raise RuntimeError(LogMsg(
                "Invalid arguments for FileOptions constructor",
                "Expected: 1. path or 2. outdir and name",
                "Received:",
                path=str(path),
                outdir=str(outdir),
                name=str(name)
            ))
        else:
            path = Path(name or f'export.xlsx')
        self._path = path

    def formatted_path(
        self, 
        *args,
        ref_date: dt.DateValue | Literal['none', 'today'] | None = None,
        how_apply_ref: fs.RenameOperation | Literal['auto'] = fs.RenameOperation.REPLACE,
        dt_fmt: str | None=None, 
        **kwargs
    ) -> Path:
        """
        - `if ref_date` resolves to `date`, applies it to construct modifed `pathstr` from `self.path.parent` `self.path.name`
        - then applies `pathstr.format(*args, **kwargs)`
        """
        return FileOptions.get_formatted_path(
            *args, 
            path=self.path, 
            ref_date=ref_date, 
            how_apply_ref=how_apply_ref, 
            dt_fmt=dt_fmt, 
            **kwargs
        )

    @staticmethod
    def get_formatted_path(
        *args,
        path: Path,
        ref_date: dt.DateValue | Literal['none', 'today'] | None = None,
        how_apply_ref: fs.RenameOperation | Literal['auto'] = fs.RenameOperation.REPLACE,
        dt_fmt: str | None=None, 
        **kwargs
    ) -> Path:
        """
        - `if ref_date` resolves to `date`, applies it to construct modifed `pathstr` from `self.path.parent` `self.path.name`
        - then applies `pathstr.format(*args, **kwargs)`
        """
        dt_fmt = dt_fmt or dt.FormatString.YMD_DOT
        pathstr = str(path)
        ref: date | None = (
            None if (ref_date is None or ref_date == 'none') 
            else dt.today() if ref_date == 'today' 
            else dt.resolve_date(ref_date)
        )
        if (ref is not None):
            pathdir = dt.resolve_optional_date_code(ref, str(path.parent))
            namestr = fs.dated_filename(path.name, ref=ref, how=how_apply_ref, fmt=dt_fmt)
            pathstr = "\\".join((pathdir, namestr))
        pathstr = pathstr.format(*args, **kwargs)
        return Path(pathstr)
    
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

    @classmethod
    def from_dict(cls, data: FileOptionsDict | dict[str, Any], /) -> Self:
        try:
            _how = data.get('how_apply_ref')
            if (_how and _how != 'auto'): 
                _how = fs.RenameOperation.resolve(_how)
            return cls(
                path=data.get("path"),
                outdir=(data.get('dir') or data.get('parent') or data.get("outdir")),
                name=data.get("name"),
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                received=Json.serialize(data)
            )) from e

    def to_dict(self) -> Json.JsonDict[FileOptionsDict]:
        return {
            "path": str(self.path),
            "name": self.name,
            "outdir": str(self.dir)
        }
    def __str__(self):
        return super().__str__()


    def exists(self):
        """ *`@returns`* `self.outpath.is_file()`"""
        return self.path.is_file()


__all__ = export(FileOptionsDict, FileOptions)

