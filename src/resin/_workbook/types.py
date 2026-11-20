"""
*`@file`* `_workbook/types`
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from pyqi._dt import (FormatString)
from pyqi._json import (stringify as json_stringify)
from pyqi import (BaseStrEnum, export)
from lute import LogMsg
from typing import (Any, TypeVar, Generic)

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
    last_refreshed_at: datetime | None
    refreshed_at: datetime | None
    publication: PublicationDisposition
    details: TDetails
    skip_reason: str | None = None
    cooldown_remaining_seconds: float = 0.0
    message: str | LogMsg | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": str(self.status),
            "path": str(self.path),
            "started_at": self.started_at.strftime(FormatString.YMD_TIME_HYPHEN),
            "ended_at": self.ended_at.strftime(FormatString.YMD_TIME_HYPHEN),
            "last_refreshed_at": (
                self.last_refreshed_at.strftime(FormatString.YMD_TIME_HYPHEN) 
                if self.last_refreshed_at 
                else None
            ),
            "publication": str(self.publication),
            "details": str(self.details),
            "skip_reason": self.skip_reason,
            "cooldown_remaining_seconds": self.cooldown_remaining_seconds,
            "message": (
                None if not self.message 
                else self.message.to_dict() if isinstance(self.message, LogMsg) 
                else self.message)
            }

    def __str__(self):
        return json_stringify(self.to_dict())

__all__ = export(
    ControllerState, 
    RefreshStatus, 
    PublicationDisposition, 
    StagingPolicy, 
    RefreshOutcome
)