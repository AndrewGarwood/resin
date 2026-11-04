"""Side-effect-free IBP options; canonical implementation for both import spellings."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from noxl.models import CellAddress

from .._workbook import ConfigurationError, StagingPolicy, validate_duration, validate_workbook_path
from .constants import ConnectionMode, DEFAULT_SHEETNAME


@dataclass(frozen=True)
class ConnectionOptions:
    name: str | None = None
    planning_area: str | None = None
    server_url: str | None = None
    is_default: bool = True
    id: str | None = None

    def __post_init__(self) -> None:
        for key in ("name", "planning_area", "server_url", "id"):
            value = getattr(self, key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ConfigurationError(f"connection {key} must be a nonempty string")
        if not isinstance(self.is_default, bool):
            raise ConfigurationError("is_default must be boolean")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ConnectionOptions:
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass(frozen=True)
class WorkbookOptions:
    path: Path
    sheetname: str = DEFAULT_SHEETNAME
    data_origin: CellAddress | None = None
    search_headers: list[str] = field(default_factory=list)
    refresh_only: bool = True
    filters: list[dict[str, Any]] = field(default_factory=list)
    desc: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", validate_workbook_path(self.path))
        if not isinstance(self.sheetname, str) or not self.sheetname.strip():
            raise ConfigurationError("sheetname must be a nonempty string")
        if self.data_origin is not None:
            try:
                address = CellAddress.from_any(self.data_origin)
            except (TypeError, ValueError, KeyError) as error:
                raise ConfigurationError("invalid data_origin cell address") from error
            if (type(address.row) is not int or type(address.col) is not int
                    or not 1 <= address.row <= 1048576 or not 1 <= address.col <= 16384):
                raise ConfigurationError("data_origin is outside Excel cell bounds")
            object.__setattr__(self, "data_origin", address)
        if not isinstance(self.search_headers, list) or not all(
            isinstance(value, str) for value in self.search_headers
        ):
            raise ConfigurationError("search_headers must be a list of strings")
        if self.refresh_only is not True:
            raise ConfigurationError("IBP writeback is unsupported; refresh_only must be true")
        if not isinstance(self.filters, list):
            raise ConfigurationError("filters must be a list")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkbookOptions:
        return cls(
            path=Path(data["path"]), sheetname=data.get("sheetname", DEFAULT_SHEETNAME),
            data_origin=data.get("data_origin"), search_headers=data.get("search_headers", []),
            refresh_only=data.get("refresh_only", True), filters=data.get("filters", []),
            desc=data.get("description", data.get("desc")),
        )

    @property
    def header_origin(self) -> CellAddress:
        if self.data_origin is None:
            raise ConfigurationError("data_origin is required for header_origin")
        return self.data_origin.offset(rows=-1)

    @property
    def info_addr(self) -> CellAddress:
        return self.header_origin.offset(rows=-1)

    @property
    def id(self) -> str:
        return self.path.stem

    def with_path(self, new_path: str | Path, /, sheetname: str | None = None) -> WorkbookOptions:
        return replace(self, path=Path(new_path), sheetname=sheetname or self.sheetname)


@dataclass(frozen=True)
class ControllerOptions:
    staging: Path
    conn: ConnectionOptions
    refresh_cooldown_minutes: float = 30
    connection_mode: ConnectionMode = ConnectionMode.WORKBOOK
    anchor_seed: Path | None = None
    anchor_sheetname: str = DEFAULT_SHEETNAME
    staging_policy: StagingPolicy | str = StagingPolicy.ALWAYS
    stage_roots: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "staging", Path(self.staging))
        object.__setattr__(self, "refresh_cooldown_minutes", validate_duration(
            self.refresh_cooldown_minutes, "refresh_cooldown_minutes", allow_zero=True
        ))
        try:
            object.__setattr__(self, "connection_mode", ConnectionMode(self.connection_mode))
        except ValueError as exc:
            raise ConfigurationError("unsupported IBP connection_mode") from exc
        try:
            object.__setattr__(self, "staging_policy", StagingPolicy(self.staging_policy))
        except ValueError as error:
            raise ConfigurationError("unsupported staging_policy") from error
        if not isinstance(self.stage_roots, (tuple, list)):
            raise ConfigurationError("stage_roots must be a sequence of filesystem paths")
        try:
            object.__setattr__(self, "stage_roots", tuple(Path(root) for root in self.stage_roots))
        except TypeError as error:
            raise ConfigurationError("stage_roots must contain filesystem paths") from error
        if not isinstance(self.conn, ConnectionOptions):
            raise ConfigurationError("conn must be ConnectionOptions")
        if not isinstance(self.anchor_sheetname, str) or not self.anchor_sheetname.strip():
            raise ConfigurationError("anchor_sheetname must be nonempty")
        if self.anchor_seed is not None:
            object.__setattr__(self, "anchor_seed", validate_workbook_path(self.anchor_seed))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ControllerOptions:
        return cls(
            staging=Path(data["staging"]), conn=ConnectionOptions.from_dict(data["connection"]),
            refresh_cooldown_minutes=data.get("refresh_cooldown_minutes", 30),
            connection_mode=data.get("connection_mode", ConnectionMode.WORKBOOK),
            anchor_seed=data.get("anchor_seed"),
            anchor_sheetname=data.get("anchor_sheetname", DEFAULT_SHEETNAME),
            staging_policy=data.get("staging_policy", StagingPolicy.ALWAYS),
            stage_roots=data.get("stage_roots", ()),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> ControllerOptions:
        with Path(path).open(encoding="utf-8") as source:
            return cls.from_dict(json.load(source))


@dataclass(frozen=True)
class RefreshInfo:
    refreshed_at: datetime
    conn_name: str
    conn_id: str | None
