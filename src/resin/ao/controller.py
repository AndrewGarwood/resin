"""
*`@file`* `ao/controller`
"""

from pathlib import Path
import time
from datetime import datetime
from typing import Any, Callable
from resin._workbook import (
    ConnectionBindingError,
    BaseController,
    Deadline,
    RefreshOutcome,
    RefreshStatus,
    SessionFactory,
    StagingPolicy,
    WorkbookControllerError,
    cooldown_remaining,
)
from resin.models._field import (resolve_field_value)
from ._options import (WorkbookOptions, ControllerOptions, ControllerOptionsDict)
from .types import (
    AoCmd, AoCommandError, AoMacro, AoProp, AoResponseCode, AoResponseTup,
    RefreshActiveStatus, WorkbookProperty,
)
from .constants import (
    COM_ADD_IN_NAME, DEFAULT_AO_DATASOURCE,
)
from resin.utils import runtime
from .utils import (
    ensure_sap_ao_ready, 
    is_busy as ao_is_busy, to_error_tuple, require_ao_bool, _probe_macro_readiness,
    error_is_clear
)
from pyqi import (Array, fs, dt, require, safe)
from lute import LogMsg, get_logger



mlog = get_logger(__file__, name_depth=1)



_UNRESOLVED = {str(AoResponseCode.DATASOURCE_INVALID), str(AoResponseCode.DATASOURCE_UNRESOLVED)}


class Controller(BaseController):
    def __init__(self,
        options: fs.StrPath | ControllerOptions | ControllerOptionsDict,
        /,
        *,
        session_factory: SessionFactory | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        pump: Callable[[], None] = runtime.pump_waiting_messages,
        now: Callable[[], datetime] = datetime.now,
    ):
        self.options = (
            options 
            if isinstance(options, ControllerOptions) 
            else ControllerOptions.from_config(options)
        )
        # self._ao_clock = clock
        # self._ao_sleep = sleep
        # self._ao_pump = pump
        super().__init__(
            options=self.options.get_base_options(),
            session_factory=session_factory,
            clock=clock, 
            sleep=sleep, 
            pump=pump, 
            now=now,
        )

    def _on_enter(self, deadline: Deadline) -> None:
        return super()._on_enter(deadline)

    def _on_exit(self) -> None:
        pass

    def _connect_com_addin(self) -> None:
        try:
            addin = self.session.get_com_addin(self.options.addin_name)
            if (not bool(addin.Connect)):
                addin.Connect = True
            if (not bool(addin.Connect)):
                raise ConnectionBindingError(
                    "Configured AO add-in is not connected",
                    msg=f"addin.Connect is False after attempting to set it to True"
                )
        except WorkbookControllerError:
            raise
        except Exception:
            raise ConnectionBindingError("Cannot connect configured AO add-in")

    def _xl_run(self, macro: str | AoMacro, *args: Any, _deadline: Deadline | None = None) -> Any:
        if _deadline is not None:
            _deadline.check("AO macro")
        self._pump()
        try:
            result = self.session.excel.Run(str(macro), *args)
        except Exception as error:
            if self.is_fatal(error):
                self.invalidate(error)
            if ao_is_busy(error): 
                raise
            raise AoCommandError(f"AO macro {macro} failed") from None
        if _deadline is not None:
            _deadline.check("AO macro")
        return result

    def _checked(
        self, 
        macro: str | AoMacro, 
        /,
        *args: Any,
        deadline: Deadline,
        responses: list[tuple[str, int]] | None = None,
    ) -> int:
        while True:
            try:
                result = self._xl_run(macro, *args, _deadline=deadline)
                break
            except Exception as error:
                if not ao_is_busy(error):
                    raise
                deadline.pause()
        if isinstance(result, bool) or not isinstance(result, (int, float)) or result != AoResponseCode.SUCCESS:
            raise AoCommandError(f"AO macro {macro} rejected the operation")
        if responses is not None:
            label = str(args[0]) if macro == AoMacro.EXEC_CMD else str(macro)
            responses.append((label, int(result)))
        return int(result)


    def _get_property(
        self, 
        prop: str | AoProp, 
        /,
        *args: Any, 
        deadline: Deadline | None = None
    ) -> Any:
        return self._xl_run(
            AoMacro.GET_PROPERTY, 
            str(prop), 
            *args, 
            _deadline=deadline
        )


    @property
    def last_error(self) -> Any:
        return self._get_property(AoProp.LAST_ERROR)

    def get_last_error(self) -> Any:
        try: return self.last_error
        except Exception: return (None, "<AO LastError unavailable>")

    def _last_error_tuple(self) -> AoResponseTup:
        return to_error_tuple(self.get_last_error())

    @property
    def changed_datasources(self) -> Any:
        return self._get_property(AoProp.CHANGED_DATASOURCES)

    @property
    def changed_crosstabs(self) -> Any:
        return self._get_property(AoProp.CHANGED_CROSSTABS)

    @property
    def is_auto_refresh_active(self) -> bool:
        return require_ao_bool(
            self._get_property(AoProp.IS_AUTO_REFRESH), 
            label=AoProp.IS_AUTO_REFRESH.value
        )


    @property
    def is_connected(self) -> bool:
        return require_ao_bool(
            self._get_property(AoProp.IS_CONNECTED), 
            label=AoProp.IS_CONNECTED.value
            )

    def is_datasource_active(self, formula_alias: str, /) -> bool:
        return require_ao_bool(
            self._get_property(AoProp.IS_DATA_SOURCE_ACTIVE, formula_alias), 
            label=AoProp.IS_DATA_SOURCE_ACTIVE.value
            )

    def get_crosstab_newline_count(self, crosstab: str = "Crosstab1", /) -> Any:
        return self._get_property(AoProp.NUMBER_OF_NEW_LINES, crosstab)

    
    def log_datasource_state(
        self, 
        ds_alias: str = DEFAULT_AO_DATASOURCE, 
        /, 
        include_last_error: bool=False
    ) -> None:
        kwargs = {
            "ds_alias": ds_alias,
            "is_active":str(safe.invoke_method(
                self, "_get_property", AoProp.IS_DATA_SOURCE_ACTIVE, ds_alias
            )),
            "is_connected":str(safe.invoke_method(
                self, "_get_property", AoProp.IS_CONNECTED, ds_alias
            )),
            "is_auto_refresh": str(safe.invoke_method(
                self, "_get_property", AoProp.IS_AUTO_REFRESH
            )),
        }
        if (include_last_error):
            kwargs["last_error"] = self.get_last_error()
        mlog.info(LogMsg(f"AO datasource state:", **kwargs))

    def wait_for_ao_ready(self, timeout_seconds: float = 90, poll_seconds: float = 1) -> None:
        deadline = self.deadline(timeout_seconds, poll_seconds)
        self.wait_for_idle(deadline)
        _probe_macro_readiness(self.session.excel, deadline)

    def _wait_datasource(self, ds_alias: str, deadline: Deadline) -> None:
        while True:
            deadline.check("AO datasource readiness")
            try:
                self.wait_for_idle(deadline)
                active = require_ao_bool(
                    self._get_property(AoProp.IS_DATA_SOURCE_ACTIVE, ds_alias, deadline=deadline),
                    label="IsDataSourceActive",
                )
                connected = require_ao_bool(
                    self._get_property(AoProp.IS_CONNECTED, ds_alias, deadline=deadline),
                    label="IsConnected",
                )
                error = self._get_property(AoProp.LAST_ERROR, deadline=deadline)
                if error_is_clear(error):
                    if active and connected: 
                        return
                elif to_error_tuple(error)[0] not in _UNRESOLVED:
                    raise AoCommandError("AO datasource readiness reported an error")
            except Exception as error:
                if (not ao_is_busy(error)): raise
            deadline.pause()
    
    def _get_workbook_info(
            self, 
            wb: Any, 
            key: WorkbookProperty | str, 
            /, 
            *, 
            deadline: Deadline | None = None
        ) -> Any:
        if deadline is not None:
            deadline.check("AO workbook property")
        wb.Activate()
        return self._xl_run(AoMacro.GET_WORKBOOK_INFO, str(key), _deadline=deadline)

    def check_workbook_prop(self, wb_source: WorkbookOptions | Any, prop: WorkbookProperty | str) -> Any:
        if isinstance(wb_source, WorkbookOptions):
            with self.operation(wb_source.path) as tx:
                self._wait_datasource(wb_source.ds_alias, tx.deadline)
                return self._get_workbook_info(tx.wb, prop, deadline=tx.deadline)
        return self._get_workbook_info(wb_source, prop)

    def get_effective_filters(self, wb_source: WorkbookOptions | Any, /) -> Any:
        if isinstance(wb_source, WorkbookOptions):
            with self.operation(wb_source.path) as tx:
                self._wait_datasource(wb_source.ds_alias, tx.deadline)
                tx.wb.Activate()
                return self._xl_run(AoMacro.LIST_EFFECTIVE_FILTERS, _deadline=tx.deadline)
        wb_source.Activate()
        return self._xl_run(AoMacro.LIST_EFFECTIVE_FILTERS)