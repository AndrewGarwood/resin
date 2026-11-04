"""Shared workbook contracts; COM objects stay at the automation boundary."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from pathlib import Path
from typing import Any, Callable, Generic, Protocol, TypeVar


class ControllerState(StrEnum):
    NEW = "new"
    ENTERING = "entering"
    READY = "ready"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


class RefreshStatus(StrEnum):
    REFRESHED = "refreshed"
    SKIPPED_COOLDOWN = "skipped_cooldown"


class PublicationDisposition(StrEnum):
    NOT_ATTEMPTED = "not_attempted"
    IN_PLACE = "in_place"
    PUBLISHED = "published"


class StagingPolicy(StrEnum):
    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


class WorkbookControllerError(RuntimeError):
    def __init__(self, message: str, **context: object) -> None:
        self.context = context
        super().__init__(message)

    def add_context(self, **context: object) -> None:
        for key, value in context.items():
            self.context.setdefault(key, value)
        self.add_note(", ".join(f"{key}={value}" for key, value in context.items()))


class ConfigurationError(WorkbookControllerError, ValueError):
    pass


class ConnectionBindingError(WorkbookControllerError):
    pass


class RefreshTimeoutError(WorkbookControllerError, TimeoutError):
    pass


class WorkbookIOError(WorkbookControllerError):
    pass


class PublicationError(WorkbookIOError):
    pass


class DeadSessionError(WorkbookControllerError):
    pass


class Session(Protocol):
    @property
    def excel(self) -> Any: ...

    @property
    def pid(self) -> int: ...

    def __enter__(self) -> Session: ...

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool: ...

    def get_com_addin(self, name: str, /) -> Any: ...

    def open_workbook(self, path: Path, /) -> Any: ...

    def add_workbook(self, path: Path, /) -> Any: ...

    def save_workbook(self, wb: Any, /, timeout: float = 20.0) -> None: ...

    def close_workbook(
        self, wb: Any, /, save_changes: bool = False
    ) -> None: ...


SessionFactory = Callable[[], Session]
TDetails = TypeVar("TDetails")


@dataclass(frozen=True)
class RefreshOutcome(Generic[TDetails]):
    status: RefreshStatus
    path: Path
    operation_id: str
    started_at: datetime
    ended_at: datetime
    elapsed_seconds: float
    previous_refreshed_at: datetime | None
    refreshed_at: datetime | None
    publication: PublicationDisposition
    details: TDetails
    skip_reason: str | None = None
    cooldown_remaining_seconds: float = 0.0


def validate_duration(
    value: object, label: str, *, allow_zero: bool = False
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"{label} must be a finite number")
    number = float(value)
    if not isfinite(number) or number < 0 or (number == 0 and not allow_zero):
        bound = "nonnegative" if allow_zero else "positive"
        raise ConfigurationError(f"{label} must be finite and {bound}")
    return number


def validate_workbook_path(
    value: str | Path, *, must_exist: bool = True
) -> Path:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise ConfigurationError("workbook path must be a nonempty string or Path")
    if str(value).lower().startswith(("http:", "https:")):
        raise ConfigurationError("HTTP(S) workbooks require a separate transport")
    path = Path(value).expanduser().resolve()
    if path.suffix.lower() not in {".xlsx", ".xlsm", ".xlsb", ".xls"}:
        raise ConfigurationError("Unsupported workbook extension", path=path)
    if must_exist and not path.is_file():
        raise ConfigurationError("Workbook does not exist", path=path)
    return path
