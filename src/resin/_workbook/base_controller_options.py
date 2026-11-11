"""
*`@file`* `_workbook/base_options`
"""
from dataclasses import dataclass
from pathlib import Path
from pyqi import (Json, fs, Array, require, export)
from typing import (Self, Any, TypedDict)
from .types import StagingPolicy
from lute import LogMsg

class BaseControllerOptionsDict(TypedDict, total=False):
    staging: str
    staging_policy: str | StagingPolicy
    stage_roots: list[str] # list of paths where, if the workbook's path is relative to the root, then the workbook should be staged.
    cooldown_seconds: float
    poll_seconds: float
    startup_timeout_seconds: float


@dataclass
class BaseControllerOptions(Json.Serial[BaseControllerOptionsDict]):
    staging: Path
    staging_policy: StagingPolicy
    stage_roots: list[Path] 
    """
    list of paths where, if the workbook's path is relative to the root, 
    then the workbook should be staged (unless `staging_policy` is `never`).
    """
    cooldown_seconds: float
    poll_seconds: float
    startup_timeout_seconds: float


    @classmethod
    def from_dict(cls, data: BaseControllerOptionsDict | dict[str, Any]) -> Self:
        try:
            return cls(
                staging=fs.to_path(data.get('staging', '')),
                staging_policy=StagingPolicy.resolve(
                    data.get('staging_policy', StagingPolicy.ALWAYS)
                ),
                stage_roots=Array.map(
                    data.get('stage_roots', []), 
                    fs.to_path
                ),
                cooldown_seconds=require.positive_number(
                    data.get('cooldown_seconds', 3600)
                ),
                poll_seconds = require.positive_number(
                    data.get('poll_seconds', 0.25)
                ),
                startup_timeout_seconds = require.positive_number(
                    data.get('startup_timeout_seconds', 90)
                )
            )
        except (KeyError, ValueError): raise
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                f"Failed to construct {cls.__name__} from dictionary.",
                received=Json.serialize(data)
            )) from e



__all__ = export(BaseControllerOptions, BaseControllerOptionsDict)