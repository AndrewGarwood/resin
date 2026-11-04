"""Side-effect-free AO configuration parsing; paths are checked, never created."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from resin._workbook import ConfigurationError, StagingPolicy, validate_duration, validate_workbook_path

from .constants import COM_ADD_IN_NAME, DEFAULT_AO_DATASOURCE


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{label} must be a nonempty string")
    return value


def _path(value: object, label: str) -> Path:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise ConfigurationError(f"{label} must be a path")
    if str(value).lower().startswith(("http:", "https:")):
        raise ConfigurationError(f"{label} must be a filesystem path")
    return Path(value).expanduser().absolute()


class WorkbookOptionsDict(TypedDict):
    filepath: str
    template: NotRequired[str]
    ds_alias: NotRequired[str]
    prompts: NotRequired[Mapping[str, Any]]
    name: NotRequired[str]
    description: NotRequired[str]
    set_prompts: NotRequired[bool]
    query: NotRequired[dict[str, Any]]


@dataclass
class WorkbookOptions:
    filepath: Path
    template: Path | None = None
    prompts: Mapping[str, Any] = field(default_factory=dict)
    ds_alias: str = DEFAULT_AO_DATASOURCE
    name: str | None = None
    desc: str | None = None
    set_prompts: bool = False
    query: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.filepath = validate_workbook_path(self.filepath)
        if self.template is not None:
            self.template = _path(self.template, "template")
            if not self.template.is_file():
                fallback = self.filepath.with_name(f"{self.filepath.stem}.template.xlsx")
                if not fallback.is_file():
                    raise ConfigurationError("template must name an existing file")
                self.template = fallback
        self.ds_alias = _text(self.ds_alias, "ds_alias")
        for label, value in (("name", self.name), ("description", self.desc)):
            if value is not None and not isinstance(value, str):
                raise ConfigurationError(f"{label} must be a string or None")
        if not isinstance(self.prompts, Mapping) or not all(isinstance(k, str) and k for k in self.prompts):
            raise ConfigurationError("prompts must be a mapping with nonempty string keys")
        self.prompts = dict(self.prompts)
        if not isinstance(self.set_prompts, bool):
            raise ConfigurationError("set_prompts must be boolean")
        if not isinstance(self.query, Mapping):
            raise ConfigurationError("query must be a mapping")
        self.query = dict(self.query)

    @property
    def key(self) -> str:
        return self.filepath.stem

    @property
    def id(self) -> str:
        template_stem = self.template.stem if self.template else self.filepath.stem
        return self.generate_id(template_stem, self.filepath.stem, self.ds_alias)

    @staticmethod
    def generate_id(template_stem: str, filepath_stem: str, ds_alias: str = DEFAULT_AO_DATASOURCE) -> str:
        return f"t({template_stem})-f({filepath_stem})-d({ds_alias})"

    @classmethod
    def from_dict(cls, data: WorkbookOptionsDict | Mapping[str, Any], /) -> WorkbookOptions:
        if "filepath" not in data:
            raise ConfigurationError("Missing required config key: filepath")
        template = data.get("template")
        return cls(
            filepath=_path(data["filepath"], "filepath"),
            template=_path(template, "template") if template else None,
            prompts=data.get("prompts", {}),
            ds_alias=data.get("ds_alias", DEFAULT_AO_DATASOURCE),
            name=data.get("name", Path(data["filepath"]).stem),
            desc=data.get("description", data.get("desc", "")),
            set_prompts=data.get("set_prompts", False),
            query=data.get("query", {}),
        )

    @staticmethod
    def validate_instance(options: WorkbookOptions, /) -> None:
        if not isinstance(options, WorkbookOptions):
            raise ConfigurationError("Expected WorkbookOptions")
        options.__post_init__()

    def template_columns(self, sep: str = "\t") -> list[str]:
        if self.template is None:
            raise ConfigurationError("template_columns requires a template")
        ext = self.template.suffix.lower()
        if ext == ".xlsx":
            from noxl.engines.pyxl.worksheet.read import find_header

            return list(find_header(self.template).headers)
        if ext not in {".txt", ".csv", ".tsv"}:
            raise ConfigurationError("Unsupported template file type")
        delimiter = "," if ext == ".csv" else "\t" if ext == ".tsv" else sep
        with self.template.open(encoding="utf-8-sig", newline="") as stream:
            return [value for row in csv.reader(stream, delimiter=delimiter) for value in row if value]


class DefaultValueOptionsDict(TypedDict, total=False):
    ds_alias: str
    datasource: str


@dataclass
class DefaultValueOptions:
    ds_alias: str = DEFAULT_AO_DATASOURCE

    def __post_init__(self) -> None:
        self.ds_alias = _text(self.ds_alias, "defaults.ds_alias")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], /) -> DefaultValueOptions:
        if not isinstance(data, Mapping):
            raise ConfigurationError("defaults must be a mapping")
        return cls(data.get("ds_alias") or data.get("datasource") or DEFAULT_AO_DATASOURCE)


class ControllerOptionsDict(TypedDict):
    staging: str
    defaults: NotRequired[DefaultValueOptionsDict]
    refresh_cooldown_minutes: NotRequired[float]
    staging_policy: NotRequired[str]
    stage_roots: NotRequired[list[str]]
    addin_name: NotRequired[str]


@dataclass
class ControllerOptions:
    staging: Path
    defaults: DefaultValueOptions = field(default_factory=DefaultValueOptions)
    refresh_cooldown_minutes: float = 30
    staging_policy: StagingPolicy | str = StagingPolicy.ALWAYS
    stage_roots: tuple[Path, ...] = ()
    addin_name: str = COM_ADD_IN_NAME

    def __post_init__(self) -> None:
        self.staging = _path(self.staging, "staging")
        if self.staging.exists() and not self.staging.is_dir():
            raise ConfigurationError("staging must name a directory")
        if not isinstance(self.defaults, DefaultValueOptions):
            raise ConfigurationError("defaults must be DefaultValueOptions")
        self.refresh_cooldown_minutes = validate_duration(
            self.refresh_cooldown_minutes, "refresh_cooldown_minutes", allow_zero=True,
        )
        try:
            self.staging_policy = StagingPolicy(self.staging_policy)
        except (ValueError, TypeError) as error:
            raise ConfigurationError("Invalid staging_policy") from error
        if not isinstance(self.stage_roots, (list, tuple)):
            raise ConfigurationError("stage_roots must be a sequence of paths")
        self.stage_roots = tuple(_path(path, "stage_roots") for path in self.stage_roots)
        self.addin_name = _text(self.addin_name, "addin_name")

    @classmethod
    def from_dict(cls, data: ControllerOptionsDict | Mapping[str, Any], /) -> ControllerOptions:
        if "staging" not in data:
            raise ConfigurationError("Missing required config key: staging")
        stage_roots = data.get("stage_roots", ())
        if not isinstance(stage_roots, (list, tuple)):
            raise ConfigurationError("stage_roots must be a sequence of paths")
        return cls(
            staging=_path(data["staging"], "staging"),
            defaults=DefaultValueOptions.from_dict(data.get("defaults", {})),
            refresh_cooldown_minutes=data.get("refresh_cooldown_minutes", 30),
            staging_policy=data.get("staging_policy", StagingPolicy.ALWAYS),
            stage_roots=tuple(_path(path, "stage_roots") for path in stage_roots),
            addin_name=data.get("addin_name", COM_ADD_IN_NAME),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> ControllerOptions:
        with Path(path).open(encoding="utf-8-sig") as stream:
            data = json.load(stream)
        if not isinstance(data, Mapping):
            raise ConfigurationError("Controller configuration must be an object")
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "staging": str(self.staging),
            "defaults": asdict(self.defaults),
            "refresh_cooldown_minutes": self.refresh_cooldown_minutes,
            "staging_policy": str(self.staging_policy),
            "stage_roots": [str(path) for path in self.stage_roots],
            "addin_name": self.addin_name,
        }


__all__ = [
    "WorkbookOptionsDict", "WorkbookOptions", "DefaultValueOptionsDict",
    "DefaultValueOptions", "ControllerOptionsDict", "ControllerOptions",
]
