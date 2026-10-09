"""
*`@file`* `resin/gui/utils/waits`
- explicit waits for idle sessions, windows, and components.
"""

from __future__ import annotations
from typing import (Literal, overload, Any, TYPE_CHECKING, TypeVar)
from ..com import runtime
from ..components.component import Component
from pyqi import Function

import lute
LogMsg = lute.LogMsg

ComponentT = TypeVar("ComponentT", bound=Component)

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
    component_cls: None=None,
    _raise: Literal[True]=True, 
    timeout: float=5.0, 
    poll_interval: float=0.1
) -> Component: ...

@overload
def wait_for_component(
    session: Session, 
    component_id: str, 
    /, 
    *, 
    component_cls: type[ComponentT],
    _raise: Literal[True]=True, 
    timeout: float=5.0, 
    poll_interval: float=0.1
) -> ComponentT: ...


@overload
def wait_for_component(
    session: Session, 
    component_id: str, 
    /, 
    *, 
    component_cls: type[ComponentT],
    _raise: Literal[False]=False, 
    timeout: float=5.0, 
    poll_interval: float=0.1
) -> ComponentT | None: ...

@overload
def wait_for_component(
    session: Session, 
    component_id: str, 
    /, 
    *, 
    component_cls: None=None,
    _raise: Literal[False]=False, 
    timeout: float=5.0, 
    poll_interval: float=0.1
) -> Component | None: ...

def wait_for_component(
    session: Session, 
    component_id: str, 
    /, 
    *, 
    component_cls: type[ComponentT] | None=None,
    _raise: bool=False, 
    timeout: float=5.0, 
    poll_interval: float=0.1
) -> Any:
    """ 
    *`@returns`* `Function.Deferred(session.find, component_id, _raise=False, component_cls=component_cls)` 
    if component is found within deadline 
    """
    return runtime.poll_until(
        Function.Deferred(session.find, component_id, _raise=False, component_cls=component_cls), 
        timeout=timeout, 
        poll_interval=poll_interval, 
        description=f"session.find({component_id})",
        _raise=_raise
    )