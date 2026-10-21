"""
*`@file`* `gui/services/pool/options`
"""
from pyqi import Json, export
from typing import (Any, Self, TypedDict)
from dataclasses import dataclass
from lute import LogMsg

class SessionPoolOptionsDict(TypedDict, total=False):
    stop_timeout: float
    worker_start_timeout: float
    prepare_timeout: float | None
    execute_timeout: float | None
    post_execute_timeout: float | None
    export_timeout: float | None

@dataclass(frozen=True, slots=True)
class SessionPoolOptions(Json.Serial[SessionPoolOptionsDict]):
    """
    *`@extends`* `Json.Serial[SessionPoolOptionsDict]`
    ```
    stop_timeout: float = 30.0
    worker_start_timeout: float = 30.0
    prepare_timeout: float | None = 120.0
    execute_timeout: float | None = 600.0
    post_execute_timeout: float | None = 120.0
    export_timeout: float | None = 300.0
    ```
    """
    stop_timeout: float = 30.0
    worker_start_timeout: float = 30.0
    prepare_timeout: float | None = 120.0
    execute_timeout: float | None = 600.0
    post_execute_timeout: float | None = 120.0
    export_timeout: float | None = 300.0

    @classmethod
    def from_dict(cls, data: SessionPoolOptionsDict | dict[str, Any]) -> Self:
        try:
            return cls(
                stop_timeout=data.get('stop_timeout') or 30.0,
                worker_start_timeout=data.get('worker_start_timeout') or 30.0,
                prepare_timeout=data.get('prepare_timeout', 120.0),
                execute_timeout=data.get('execute_timeout', 900.0),
                post_execute_timeout=data.get('post_execute_timeout', 120.0),
                export_timeout=data.get('export_timeout', 300.0),
            )
        except Exception as e:
            raise RuntimeError(LogMsg.err(
                e, 
                received=Json.serialize(data)
            )) from e

__all__ = export(SessionPoolOptions, SessionPoolOptionsDict)