"""
*`@file`* `gui/core/session_info`
"""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionInfo:
    transaction: str
    response_time_ms: int
    system_session_id: str
    user: str
    system_name: str
    system_number: int
    application_server: str
    client: str
    screen_number: int
    session_number: int
    


__all__ = ["SessionInfo"]