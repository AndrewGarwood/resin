"""
*`@file`* `_workbook/types`
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from pyqi import BaseStrEnum, export
from lute import LogMsg
from typing import (TypeVar, Generic)

class ControllerState(BaseStrEnum):
    """
    ```
    NEW = "new"
    ENTERING = "entering"
    READY = "ready"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"
    ```
    """
    NEW = "new"
    ENTERING = "entering"
    READY = "ready"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


class RefreshStatus(BaseStrEnum):
    """
    ```
    REFRESHED = "refreshed"
    SKIPPED_COOLDOWN = "skipped_cooldown"
    ```
    """
    REFRESHED = "refreshed"
    SKIPPED_COOLDOWN = "skipped_cooldown"


class PublicationDisposition(BaseStrEnum):
    """
    ```
    NOT_ATTEMPTED = "not_attempted"
    IN_PLACE = "in_place"
    PUBLISHED = "published"
    ```
    """
    NOT_ATTEMPTED = "not_attempted"
    IN_PLACE = "in_place"
    PUBLISHED = "published"


class StagingPolicy(BaseStrEnum):
    """
    ```
    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"
    ```
    """
    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"

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
    message: str | LogMsg | None = None

__all__ = export(
    ControllerState, RefreshStatus, 
    PublicationDisposition, StagingPolicy, 
    RefreshOutcome
)