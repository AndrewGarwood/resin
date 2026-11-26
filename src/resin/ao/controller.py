"""
*`@file`* `ao/controller`
"""
from __future__ import annotations
import time
from datetime import datetime
from typing import (Any, Callable, Literal, Mapping)
from resin._workbook import (
    ConnectionBindingError,
    BaseController,
    Deadline,
    RefreshOutcome,
    RefreshStatus,
    SessionFactory,
    WorkbookControllerError,
    cooldown_remaining,
    parse_refresh_timestamp
)
from resin.models import _field
from ._options import (ControllerOptions, ControllerOptionsDict)
from .workbook_options import (WorkbookOptions)
from .types import (
    AoCmd, AoCommandError, AoMacro, AoProp, AoRefreshDetails, AoResponseCode, AoResponseTup,
    RefreshActiveStatus, WorkbookProperty,
)
from .constants import (
    DEFAULT_AO_DATASOURCE,
)
from resin.utils import runtime
from .utils import (
    is_busy as ao_is_busy, to_error_tuple, require_ao_bool, _probe_macro_readiness,
    error_is_clear
)
from pyqi import (Array, require, safe, guard, Function, Json)
from lute import LogMsg, get_logger

mlog = get_logger(__file__, name_depth=1)


_UNRESOLVED = {
    str(AoResponseCode.DATASOURCE_INVALID), 
    str(AoResponseCode.DATASOURCE_UNRESOLVED)
}


class Controller(BaseController):
    def __init__(self,
        options: ControllerOptions | Json.ObjectSource[ControllerOptionsDict],
        *,
        session_factory: SessionFactory | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        pump: Callable[[], None] = runtime.pump_waiting_messages,
        now: Callable[[], datetime] = datetime.now,
    ):
        self.options = ControllerOptions.from_object_source(options)
        super().__init__(
            options=self.options,
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

    def _xl_run(self, macro: str | AoMacro, /, *args: Any, _deadline: Deadline | None = None) -> Any:
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
                if not ao_is_busy(error): raise
                deadline.pause()
        if not guard.is_number(result) or result != AoResponseCode.SUCCESS:
            raise AoCommandError(f"AO macro {macro} rejected the operation")
        if responses is not None:
            label = str(args[0]) if macro == AoMacro.EXEC_CMD else str(macro)
            responses.append((label, int(result)))
        return int(result)
    
    def _exec_cmd(self, cmd: str | AoCmd, /, *args: Any) -> int:
        return self._checked(AoMacro.EXEC_CMD, str(cmd), *args, deadline=self.deadline(30))


    def _get_property(
        self, 
        prop: str | AoProp, 
        /,
        *args: Any, 
        deadline: Deadline | None = None
    ) -> Any:
        """
        [SAPGetProperty](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f27123b76c9b1014bf2c9a7eb0e91070.html)
        - e.g. `Application.Run("SAPGetProperty", "IsConnected", "DS_1")`
        """
        return self._xl_run(
            AoMacro.GET_PROPERTY, 
            str(prop), 
            *args, 
            _deadline=deadline
        )


    @property
    def last_error(self) -> Any:
        """
        [LastError information](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f270f7eb6c9b1014bf2c9a7eb0e91070.html)
        """
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
        """ deadline check of datasource `active` and `connected` props """
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
        """
        *`@param`* `wb (Any)` - Excel Workbook com object. (e.g. `win32com.client.CDispatch`)
        """
        if deadline is not None:
            deadline.check("AO workbook property")
        wb.Activate()
        return self._xl_run(
            AoMacro.GET_WORKBOOK_INFO, 
            str(key), 
            _deadline=deadline
        )

    def check_workbook_prop(
        self, 
        wb_source: WorkbookOptions | Any, 
        prop: WorkbookProperty | str,
        /,
    ) -> Any:
        if isinstance(wb_source, WorkbookOptions):
            with self.operation(wb_source.path) as tx:
                self._wait_datasource(wb_source.ds_alias, tx.deadline)
                return self._get_workbook_info(tx.wb, prop, deadline=tx.deadline)
        return self._get_workbook_info(wb_source, prop)

    def get_effective_filters(self, wb_source: WorkbookOptions | Any, /) -> Any:
        if isinstance(wb_source, WorkbookOptions):
            with self.operation(wb_source.path) as txn:
                self._wait_datasource(wb_source.ds_alias, txn.deadline)
                txn.wb.Activate()
                return self._xl_run(AoMacro.LIST_EFFECTIVE_FILTERS, _deadline=txn.deadline)
        wb_source.Activate()
        return self._xl_run(AoMacro.LIST_EFFECTIVE_FILTERS)

    def _timestamp(
        self, 
        wb: Any, 
        deadline: Deadline | None = None
    ) -> datetime | None:
        value = self._get_workbook_info(
            wb, 
            WorkbookProperty.LAST_REFRESHED_AT, 
            deadline=deadline
        )
        return parse_refresh_timestamp(value, use_1904_epoch=bool(wb.Date1904))

    def get_last_refreshed_at(self, target: WorkbookOptions | Any, /) -> datetime | None:
        if isinstance(target, WorkbookOptions):
            with self.operation(target.path) as txn:
                self._wait_datasource(target.ds_alias, txn.deadline)
                return self._timestamp(txn.wb, txn.deadline)
        return self._timestamp(target)

    def set_variable(
        self, 
        key: str, 
        value: Any, 
        /,
        ds_alias: str = DEFAULT_AO_DATASOURCE,
        value_fmt: str = "",
        timeout_seconds: float = 20,
        poll_seconds: float = 1,
        *,
        resolve_value: bool = True,
        _deadline: Deadline | None = None,
        _responses: list[tuple[str, int]] | None = None,
    ) -> int:
        if not isinstance(resolve_value, bool):
            raise AoCommandError("resolve_value must be boolean")
        resolved = (
            _field.resolve_field_value(value) if resolve_value else value
            )
        deadline = _deadline if _deadline is not None else self.deadline(timeout_seconds, poll_seconds)
        while True:
            deadline.check("AO set prompt")
            try:
                result = self._xl_run(AoMacro.SET_VAR, key, resolved, value_fmt, ds_alias, _deadline=deadline)
                if guard.is_number(result) and result == AoResponseCode.SUCCESS:
                    if _responses is not None:
                        _responses.append((str(AoMacro.SET_VAR), int(result)))
                    return int(result)
                code, _ = to_error_tuple(self._get_property(AoProp.LAST_ERROR, deadline=deadline))
                if code not in _UNRESOLVED:
                    raise AoCommandError("AO rejected prompt")
            except Exception as error:
                if not ao_is_busy(error): raise
            deadline.pause()

    def clear_variable(
        self, 
        key: str, 
        /, 
        ds_alias: str = DEFAULT_AO_DATASOURCE,
        timeout_seconds: float = 20, 
        poll_seconds: float = 1,
    ) -> int:
        return self.set_variable(
            key, 
            "", 
            ds_alias, 
            timeout_seconds=timeout_seconds, 
            poll_seconds=poll_seconds, 
            resolve_value=False
        )

    def _set_refresh_behaviour(self, state: Literal["On", "Off"], /) -> int:
        return self._checked(AoMacro.SET_REFRESH, state, deadline=self.deadline(30))

    def _set_pause_variable_submission(self, state: Literal["On", "Off"], /) -> int:
        return self._exec_cmd(AoCmd.PAUSE_VARIABLE_SUBMIT, state)

    def _set_auto_refresh(self, state: Literal["On", "Off"], /, *ds_alias: str) -> int:
        return self._exec_cmd(AoCmd.SET_AUTOREFRESH, state, ";".join(ds_alias))



    def _refresh_status(
        self, 
        status: RefreshActiveStatus, 
        /,
        deadline: Deadline,
        responses: list[tuple[str, int]] | None = None,
    ) -> None:
        status = RefreshActiveStatus(status)
        refresh, pause = (
            ("On", "Off") if status == RefreshActiveStatus.ACTIVE 
            else ("Off", "On")
        )
        self._checked(
            AoMacro.SET_REFRESH, 
            refresh, 
            deadline=deadline, 
            responses=responses
        )
        self._checked(
            AoMacro.EXEC_CMD, 
            str(AoCmd.PAUSE_VARIABLE_SUBMIT), 
            pause, 
            deadline=deadline, 
            responses=responses
        )

    def _restore_refresh(self, deadline: Deadline) -> None:
        errors: list[Exception] = []
        _actions = (
            (AoMacro.SET_REFRESH, ("On",)),
            (AoMacro.EXEC_CMD, (str(AoCmd.PAUSE_VARIABLE_SUBMIT), "Off")),
        )
        for macro, args in _actions:
            try: self._checked(macro, *args, deadline=deadline)
            except Exception as e: errors.append(e)
        if errors:
            self.invalidate(errors[0])
            raise errors[0]
        
    def set_refresh_active_status(self, status: RefreshActiveStatus, /, sleep: int = 1) -> None:
        """
        - `status == 'active'` → set `SAPSetRefreshBehaviour` to `"On"` and 
        `PauseVariableSubmit` to `"Off"`
        - `status == 'inactive' →` set `SAPSetRefreshBehaviour` to `"Off"` and 
        `PauseVariableSubmit` to `"On"`
        - [SAPSetRefreshBehaviour](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/f27144cb6c9b1014bf2c9a7eb0e91070.html)
        """
        deadline = self.deadline(30)
        self._refresh_status(status, deadline)
        if sleep:
            deadline.pause(require.non_negative_number(
                sleep, 
                name="set_refresh_active_status(..., <sleep: int>)"
            ))

    def refresh_data(self) -> int:
        """ **legacy/deprecated** """
        return self._exec_cmd(AoCmd.REFRESH_DATA)

    def open_server_workbook(self, name: str, /) -> int:
        """ 
        **deprecated**

        [SAPOpenWorkbook](https://help.sap.com/docs/SAP_ANALYSIS_OFFICE_CLOUD/b25c777a2c8c4e3da2f472cce24f289c/be80187d96c446918da97660d2655573.html) 
        
        *`@param`* `name (str)` - "technical name of the document."
            - `if from SAP BW server:` "this is the technical name as is it is shown in the Open dialog"
            - `if from BI platform:` "it is the CUID that can be found in the general properties of an Analysis workbook in the CMC"
        
        - "After the command execution, the opened workbook is active." (assuming success)
        """
        return self._checked(AoMacro.OPEN_WORKBOOK, name, deadline=self.deadline(30))

    def _wait_completion(
        self, 
        wb: Any, 
        ds_alias: str, 
        baseline: datetime | None, 
        deadline: Deadline
    ) -> datetime:
        while True:
            self._wait_datasource(ds_alias, deadline)
            try:
                observed = self._timestamp(wb, deadline)
                if observed is not None and (baseline is None or observed > baseline):
                    # Check again after reading metadata; a timestamp alone is insufficient.
                    self.wait_for_idle(deadline)
                    if not error_is_clear(self._get_property(AoProp.LAST_ERROR, deadline=deadline)):
                        raise AoCommandError("AO completion reported an error")
                    return observed
            except Exception as e:
                if not ao_is_busy(e):
                    raise
            deadline.pause()

    def refresh(
        self, 
        wbo: WorkbookOptions, 
        /, 
        set_prompts: bool | None = None,
        timeout_minutes: float = 30, 
        force: bool = False, 
        *,
        resolve_prompts: bool = True,
    ) -> RefreshOutcome[AoRefreshDetails]:
        if not isinstance(force, bool) or not isinstance(resolve_prompts, bool):
            raise AoCommandError("force and resolve_prompts must be boolean")
        apply_prompts = wbo.set_prompts if set_prompts is None else set_prompts
        if not isinstance(apply_prompts, bool):
            raise AoCommandError("set_prompts must be boolean")
        
        with self.operation(wbo.path, timeout_minutes=timeout_minutes) as txn:
            txn.phase = "AO datasource readiness"
            txn.wb.Activate()
            self._wait_datasource(wbo.ds_alias, txn.deadline)
            previous = self._timestamp(txn.wb, txn.deadline)
            txn.last_timestamp = previous
            remaining = cooldown_remaining(
                previous, 
                self._now(), 
                self.options.cooldown_seconds, 
                force=force
            )
            if remaining > 0:
                return txn.outcome(
                    RefreshStatus.SKIPPED_COOLDOWN, 
                    previous, 
                    previous,
                    AoRefreshDetails(wbo.ds_alias), 
                    skip_reason="cooldown",
                    cooldown_remaining_seconds=remaining,
                )
            prompts: Mapping[str, Any] = wbo.prompts if apply_prompts else {}
            resolved: dict[str, Any] = dict()
            responses: list[tuple[str, int]] = []
            txn.phase = "AO initial refresh"
            self._checked(
                AoMacro.EXEC_CMD, 
                str(AoCmd.REFRESH_DATA), 
                deadline=txn.deadline, 
                responses=responses
            )
            initial = self._wait_completion(txn.wb, wbo.ds_alias, previous, txn.deadline)
            txn.last_timestamp = initial
            restoration_needed = True
            original_error: BaseException | None = None
            try:
                txn.phase = "AO pausing prompts"
                self._refresh_status(RefreshActiveStatus.INACTIVE, txn.deadline, responses)
                txn.phase = "AO prompts"
                for key, value in prompts.items():
                    _resolved_value = _field.resolve_field_value(value)
                    if (Array.isArray(_resolved_value)):
                        raise NotImplementedError(LogMsg(
                            f"Setting multiple values for single parameter not yet handled"
                        ))
                    self.set_variable(
                        key, 
                        value, 
                        wbo.ds_alias, 
                        resolve_value=resolve_prompts,
                        _deadline=txn.deadline,
                        _responses=responses,
                    )
                    resolved[key] = _resolved_value
                
                txn.phase = "AO resuming prompts"
                self._refresh_status(RefreshActiveStatus.ACTIVE, txn.deadline, responses)
                restoration_needed = False
                self._wait_datasource(wbo.ds_alias, txn.deadline)
                baseline = self._timestamp(txn.wb, txn.deadline)
                if baseline is None or baseline < initial:
                    raise AoCommandError("AO refresh timestamp regressed before final refresh")
                txn.phase = "AO final refresh"
                self._checked(
                    AoMacro.EXEC_CMD, 
                    str(AoCmd.REFRESH_DATA), 
                    deadline=txn.deadline, 
                    responses=responses
                )
                refreshed = self._wait_completion(txn.wb, wbo.ds_alias, baseline, txn.deadline)
                txn.last_timestamp = refreshed
            except BaseException as e:
                original_error = e
                raise
            finally:
                if restoration_needed:
                    try:
                        # Do not silently extend an exhausted operation deadline.
                        self._restore_refresh(txn.deadline)
                    except Exception as restoration_error:
                        self.invalidate(restoration_error)
                        if original_error is None:
                            raise
            txn.phase = "AO publication"
            txn.commit()
            return txn.outcome(
                RefreshStatus.REFRESHED, 
                previous, 
                refreshed,
                AoRefreshDetails(
                    wbo.ds_alias, 
                    tuple(resolved), 
                    tuple(responses), 
                    completion_verified=True,
                    last_data_update_max=safe.execute_deferred(
                        Function.Deferred(
                            self._xl_run, 
                            AoMacro.GET_SRC_INFO, 
                            "LastDataUpdateMaximum"
                        )
                    ),
                    last_data_update=safe.execute_deferred(
                        Function.Deferred(
                            self._xl_run, 
                            AoMacro.GET_SRC_INFO, 
                            "LastDataUpdate"
                        )
                    )
                ),
            )

