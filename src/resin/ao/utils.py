"""
*`@file`* `ao/utils`
"""

import time
from typing import Any, Callable, Sequence

from pyqi import require, export

from resin._workbook.deadline import Deadline
from resin._workbook.exceptions import (
    ConnectionBindingError, 
    WorkbookControllerError, 
    ExcelComValueError
)
from resin._workbook.utils import is_excel_error_value
from .constants import BUSY_HRESULTS, COM_ADD_IN_NAME
from .types import (AoResponseTup, AoMacro, AoProp, AoCommandError)
from resin.utils import runtime


def require_ao_bool(value: object, /, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if is_excel_error_value(value):
        raise ExcelComValueError(f"{label} returned an Excel error")
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    raise AoCommandError(f"{label} returned a non-boolean AO value")

def is_busy(error: Exception) -> bool:
    hresult = getattr(error, "hresult", None)
    if hresult is None and error.args:
        hresult = error.args[0]
    return isinstance(hresult, int) and hresult in BUSY_HRESULTS


def to_error_tuple(value: Any, /) -> AoResponseTup:
    while isinstance(value, (tuple, list)) and len(value) == 1:
        value = value[0]
    if value is None or value == "":
        return None, None
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) >= 2:
            return str(value[0]) if value[0] is not None else None, str(value[1])
    return str(value), None

def error_is_clear(value: Any, /) -> bool:
    code, message = to_error_tuple(value)
    return code in (None, "", "0", "0.0") and message in (None, "", "None")

def _probe_macro_readiness(excel: Any, deadline: Deadline, /):
    op_label = "AO macro readiness"
    while True:
        deadline.check("AO macro readiness")
        try:
            excel.Run(AoMacro.GET_PROPERTY.value, AoProp.LAST_ERROR.value)
        except Exception as e:
            if (not is_busy(e)):
                raise ConnectionBindingError("")
            deadline.pause()
        else:
            deadline.check(op_label)
            return


def ensure_sap_ao_ready(
    excel: Any,
    *,
    timeout_seconds: float = 90,
    poll_seconds: float = 1,
    addin_name: str = COM_ADD_IN_NAME,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    pump: Callable[[], None] = runtime.pump_waiting_messages,
) -> None:
    """Probe only the exact configured add-in in a borrowed Excel instance."""
    deadline = Deadline(
        require.positive_number(timeout_seconds, "timeout_seconds"),
        clock=clock, sleep=sleep, pump=pump,
        poll_seconds=require.positive_number(poll_seconds, "poll_seconds"),
    )
    try:
        addin = excel.COMAddIns.Item(addin_name)
        if not bool(addin.Connect):
            addin.Connect = True
        if not bool(addin.Connect):
            raise ConnectionBindingError("Configured AO add-in is not connected")
    except WorkbookControllerError:
        raise
    except Exception:
        raise ConnectionBindingError("Cannot connect configured AO add-in") from None
    _probe_macro_readiness(excel, deadline)

__all__ = export(
    is_busy, 
    error_is_clear, 
    ensure_sap_ao_ready, 
    to_error_tuple, 
    require_ao_bool
)