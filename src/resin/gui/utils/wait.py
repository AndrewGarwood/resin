"""
*`@file`* `resin/gui/utils/waits`
- explicit waits for idle sessions, windows, and components.
"""

from __future__ import annotations
from typing import (Literal, overload, Any, TYPE_CHECKING)
from ..com import runtime
from ..components.component import Component
from pyqi import Function

import lute
LogMsg = lute.LogMsg

if TYPE_CHECKING:
    from ..core.session import (Session)

# wait_for_session_idle = Session.wait_for_idle # muh color...
# def wait_for_session_idle(
#     session: Session, 
#     /,
#     *, 
#     timeout: float=60.0, 
#     poll_interval: float=0.05
# ) -> Session:
#     return Session.wait_for_idle(session, timeout=timeout, poll_interval=poll_interval)


@overload
def wait_for_component(
    session: Session, 
    component_id: str, 
    /, 
    *, 
    strict: Literal[True]=True, 
    timeout: float=5.0, 
    poll_interval: float=0.1
) -> Component: ...

@overload
def wait_for_component(
    session: Session, 
    component_id: str, 
    /, 
    *, 
    strict: Literal[False]=False, 
    timeout: float=5.0, 
    poll_interval: float=0.1
) -> Component | None: ...

def wait_for_component(
    session: Session, 
    component_id: str, 
    /, 
    *, 
    strict: bool=False, 
    timeout: float=5.0, 
    poll_interval: float=0.1
) -> Any:
    return runtime.poll_until(
        Function.Deferred(session.find, component_id, _raise=False), 
        timeout=timeout, 
        poll_interval=poll_interval, 
        description=f"session.find({component_id})",
        strict=strict
    )