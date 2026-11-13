"""
*`@file`* `_workbook/base_options`
"""
from dataclasses import dataclass
from pathlib import Path
from pyqi import (Json, fs, Array, require, export)
from typing import (Self, Any, TypedDict, Required)
from .types import StagingPolicy
from lute import LogMsg

class BaseControllerOptionsDict(TypedDict, total=False):
    staging: Required[str]
    staging_policy: str | StagingPolicy
    stage_roots: list[str]
    cooldown_seconds: float
    poll_seconds: float
    startup_timeout_seconds: float


@dataclass
class BaseControllerOptions(Json.Serial[BaseControllerOptionsDict]):
    """
    *`@extends`* `Json.Serial[BaseControllerOptionsDict]`
    """
    staging: Path
    staging_policy: StagingPolicy
    stage_roots: list[Path] 
    """
    list of paths where, if the workbook's path is relative to the root, 
    then the workbook should be staged (unless `staging_policy` is `never`).
    """
    cooldown_seconds: float = 3600
    poll_seconds: float = 0.25
    startup_timeout_seconds: float = 90


    @classmethod
    def from_dict(cls, data: BaseControllerOptionsDict | dict[str, Any], /) -> Self:
        try:
            return cls(
                **cls.read_base_entries(data)
                # staging=fs.to_path(data['staging']),
                # staging_policy=StagingPolicy.resolve(
                #     data.get('staging_policy', StagingPolicy.ALWAYS)
                # ),
                # stage_roots=Array.map(
                #     data.get('stage_roots', []), 
                #     fs.to_path
                # ),
                # cooldown_seconds=require.positive_number(
                #     data.get('cooldown_seconds', 3600)
                # ),
                # poll_seconds = require.positive_number(
                #     data.get('poll_seconds', 0.25)
                # ),
                # startup_timeout_seconds = require.positive_number(
                #     data.get('startup_timeout_seconds', 90)
                # )
            )
        except (KeyError, ValueError): raise
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                f"Failed to construct {cls.__name__} from dictionary.",
                received=Json.serialize(data)
            )) from e

    @staticmethod
    def read_base_entries(data: BaseControllerOptionsDict | dict[str, Any], /):
        """
        ```
        staging: Required[str] # → Path
        staging_policy: str | StagingPolicy # → StagingPolicy
        stage_roots: list[str] # → list[Path]
        cooldown_seconds: float # → float
        poll_seconds: float # → float
        startup_timeout_seconds: float # → float
        ```
        """
        return {
            "staging": fs.to_path(data['staging']),
            "staging_policy": StagingPolicy.resolve(
                data.get('staging_policy', StagingPolicy.ALWAYS)
            ),
            "stage_roots": Array.map(
                data.get('stage_roots', []), 
                fs.to_path
            ),
            "cooldown_seconds": require.positive_number(
                data.get('cooldown_seconds', 3600)
            ),
            "poll_seconds": require.positive_number(
                data.get('poll_seconds', 0.25)
            ),
            "startup_timeout_seconds": require.positive_number(
                data.get('startup_timeout_seconds', 90)
            )
        }



__all__ = export(BaseControllerOptions, BaseControllerOptionsDict)