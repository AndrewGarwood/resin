"""
*`@file`* `utils/winauto/window/find`
"""
from typing import Any, overload, Literal, TypeVar, TypeGuard
import re
import sys
from resin.utils.winauto.types import (DesktopBackend, ElementSelector)
from resin.utils.runtime import validate_polling
from resin.utils.winauto.exceptions import (AutomationError)
from pywinauto import Desktop, WindowSpecification, Application
from pywinauto.base_wrapper import BaseWrapper
from pywinauto.controls.hwndwrapper import (DialogWrapper, HwndWrapper)
from .options import (WindowOptionsDict, WindowCriteria)
from .utils import (resolve_window_options_dict, resolve_window_specification)
from pyqi import (
    export,
)
from lute import (get_logger, LogMsg, annotate)

WrapperT = TypeVar("WrapperT", bound=BaseWrapper)

mlog = get_logger(__file__, name_depth=1)

@overload
def find(
    criteria: WindowCriteria,
    /,
    *,
    app: Application | None=None,
    backend: DesktopBackend | str | None = None,
    require_unique: bool = True,
    strict: Literal[True]=True,
    selector: ElementSelector | None = None,
    expected_wrapper: None = None
) -> BaseWrapper | Any: ...

@overload
def find(
    criteria: WindowCriteria,
    /,
    *,
    app: Application | None=None,
    backend: DesktopBackend | str | None = None,
    require_unique: bool = True,
    strict: Literal[True]=True,
    selector: ElementSelector | None = None,
    expected_wrapper: type[WrapperT] = BaseWrapper
) -> WrapperT: ...

@overload
def find(
    criteria: WindowCriteria,
    /,
    *,
    app: Application | None=None,
    backend: DesktopBackend | str | None = None,
    require_unique: bool = True,
    strict: Literal[False],
    selector: ElementSelector | None = None,
    expected_wrapper: None = None
) -> BaseWrapper | Any | None: ...

@overload
def find(
    criteria: WindowCriteria,
    /,
    *,
    app: Application | None=None,
    backend: DesktopBackend | str | None = None,
    require_unique: bool = True,
    strict: Literal[False],
    selector: ElementSelector | None = None,
    expected_wrapper: type[WrapperT] = BaseWrapper
) -> WrapperT | None: ...

def find(
    criteria: WindowCriteria,
    /,
    *,
    app: Application | None=None,
    backend: DesktopBackend | str | None = None,
    require_unique: bool = True,
    strict: bool = True,
    selector: ElementSelector | None = None,
    expected_wrapper: type[WrapperT] | None = None
):
    """
    calls `(app or Desktop(backend=backend)).windows(**kwargs) -> list[Unknown]`

    - *`@param`* `criteria (WindowOptionsInput = str | Pattern[str] | int | WindowOptionsDict)`
        - `int` → `WindowOptionsDict(handle=criteria)`
        - `str` → `WindowOptionsDict(title=criteria)`
        - `Pattern[str]` → `WindowOptionsDict(title_re=criteria.pattern)`
        - `WindowOptionsDict` → `WindowOptionsDict`
    - *`@param`* `app (pywinauto.application.Application)`
        - e.g. `Application(backend=backend).connect(process=pid, timeout=timeout)`
    - *`@param`* `strict (bool)` whether to raise error if element not found
    """
    result: Any | None = None
    error: Exception | None = None
    candidates: list[BaseWrapper] | None = None
    options = resolve_window_options_dict(criteria) if criteria is not None else dict()
    try:
        # mlog.debug(LogMsg(f"WindowOptions: {options}"))
        candidates = (app or Desktop(backend=backend)).windows(**options)
        # mlog.debug(LogMsg(f"Found {len(candidates)} candidate(s)"))
        result = _select_element(
            candidates, 
            strict=strict, 
            require_unique=require_unique, 
            selector=selector
        )
    except Exception as e:
        error = e
    if (strict and result is None):
        raise AutomationError(LogMsg.err(
            (error or ValueError("element not found")), 
            f"Unable to find target element",
            criteria=str(options),
            backend=backend,
            selector=annotate(selector),
            strict=strict,
            require_unique=require_unique,
            candidates=annotate(candidates),
            result=result
        ))
    if (expected_wrapper is not None
        and result is not None 
        and not isinstance(result, expected_wrapper)
        ):
        raise AutomationError(LogMsg.err(
            TypeError("Found element with unexpected wrapper class"),
            "Failed to find element with target wrapper class",
            expected_wrapper=annotate(expected_wrapper),
            criteria=str(options),
            backend=backend,
            selector=annotate(selector),
            strict=strict,
            require_unique=require_unique,
            candidates=annotate(candidates),
            result=annotate(result),
        ))
    return result

def _select_element(
    candidates: list[Any], 
    /,
    *, 
    strict: bool = True,
    require_unique: bool = True,
    selector: ElementSelector | None = None,
) -> Any | None:
    if (not candidates):
        if (strict):
            raise AutomationError("no candidate windows found")
        return None
    if (len(candidates) == 1):
        return candidates[0]
    # → len(candidates) > 1
    if (selector is not None):
        return selector(candidates)
    if (require_unique):
        raise AutomationError(
            f"require_unique==True and found {len(candidates)} candidates"
        )
    return candidates[0]


@overload
def by_spec(
    spec: WindowCriteria | WindowSpecification, 
    /, 
    *, 
    backend: DesktopBackend | str | None = None,
    strict: Literal[True] = True,
    timeout: float=10.0,
    retry_interval: float=1.0,
    expected_wrapper: type[WrapperT] | None = BaseWrapper
) -> WrapperT: ...

@overload
def by_spec(
    spec: WindowCriteria | WindowSpecification, 
    /, 
    *, 
    backend: DesktopBackend | str | None = None,
    strict: Literal[False],
    timeout: float=10.0,
    retry_interval: float=1.0,
    expected_wrapper: type[WrapperT] | None = BaseWrapper
) -> WrapperT | None: ...


def by_spec(
    spec: WindowCriteria | WindowSpecification, 
    /, 
    *, 
    backend: DesktopBackend | str | None = None,
    strict: bool = True,
    timeout: float=10.0,
    retry_interval: float=1.0,
    expected_wrapper: type[WrapperT] | None = BaseWrapper
): 
    """
    calls `pywinauto.Desktop().window()` 
    - only checks for `WindowSpecification.exists()`, then gets `spec.wrapper_object() -> Unknown`
    - *`@param`* `timeout (float)` seconds
    - *`@param`* `retry_interval (float)` seconds
    - *`@param`* `strict (bool)` whether to raise error if element not found
    - *`@param`* `expected_wrapper (type[WrapperT], bound=BaseWrapper) default=BaseWrapper`
        - **raise** exception if `expected_wrapper` is defined and value found is not `instanceof` this type.
        - e.g. `pywinauto.controls.hwndwrapper.DialogWrapper`
    """
    timeout, retry_interval = validate_polling(timeout, retry_interval)
    try:
        spec = resolve_window_specification(spec, backend=backend)
        if (not spec.exists(
            timeout=timeout, 
            retry_interval=retry_interval
        )):
            if (strict):
                raise AutomationError(LogMsg(
                    "spec.exists() returned False after wait time"
                ))
            return None
        
        result = spec.wrapper_object()
        if (expected_wrapper is None):
            return result
        if (not isinstance(result, expected_wrapper)):
            raise TypeError(LogMsg(
                "Found element with unexpected wrapper class",
                ))
        return result
    except Exception as e:
        raise AutomationError(LogMsg.err(e,
            spec=str(spec),
            backend=backend,
            timeout=timeout,
            poll=retry_interval,
            expected_wrapper=annotate(expected_wrapper)
        )) from e


__all__ = export(
    find,
    by_spec
)