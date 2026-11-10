"""
*`@file`* `_workbook/types`
"""

from dataclasses import dataclass
from pathlib import Path
from pyqi import BaseStrEnum, export
from typing import (Protocol, TypeVar, Generic, TypeAlias, Callable, Any, Self)

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


__all__ = export(
    ControllerState, RefreshStatus, 
    PublicationDisposition, StagingPolicy, 
)