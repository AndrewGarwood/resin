"""AO automation through an owned workbook transaction.

Completion deliberately requires LastRefreshedAt to advance for both refreshes,
plus a connected, active datasource, clear LastError and idle Excel. This is a
conservative fake-COM-tested predicate, not a live-validated SAP guarantee.
Workbooks whose AO version does not advance that timestamp fail closed.

There is no supported getter for both refresh-behaviour/pause settings. On exit
from the prompt section we therefore use the explicit safe restoration pair:
refresh behaviour On, variable submission pause Off. Unlike the inverted legacy
status implementation, INACTIVE actually pauses submission (Off, On).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Self

from resin._workbook import (
    ConnectionBindingError,
    ControllerBase,
    Deadline,
    RefreshOutcome,
    RefreshStatus,
    SessionFactory,
    StagingPolicy,
    WorkbookControllerError,
    cooldown_remaining,
    parse_refresh_timestamp,
    validate_duration,
)
from resin.models import _field

from .constants import (
    AoCmd, AoMacro, AoProp, AoResponseCode, AoResponseTup,
    COM_ADD_IN_NAME, DEFAULT_AO_DATASOURCE, RefreshActiveStatus, WorkbookProperty,
)
from ._options import ControllerOptions, WorkbookOptions

_LOG = logging.getLogger(__name__)
_BUSY_HRESULTS = {-2147418111, -2147417846, -2146777998}
_UNRESOLVED = {str(AoResponseCode.DATASOURCE_INVALID), str(AoResponseCode.DATASOURCE_UNRESOLVED)}


class AoCommandError(WorkbookControllerError):
    """AO rejected a command, prompt or completion observation."""


class ExcelComValueError(WorkbookControllerError):
    """AO returned an Excel error instead of a scalar value."""


@dataclass(frozen=True)
class AoRefreshDetails:
    ds_alias: str
    prompts_applied: tuple[str, ...] = ()
    command_responses: tuple[tuple[str, int], ...] = ()
    completion_verified: bool = False
    live_semantics_verified: bool = False


def is_excel_error_value(value: object, /) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and -2146827000 < value < -2146826000


def require_ao_bool(value: object, /, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if is_excel_error_value(value):
        raise ExcelComValueError(f"{label} returned an Excel error")
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    raise AoCommandError(f"{label} returned a non-boolean AO value")


def _pump_messages() -> None:
    import pythoncom

    pythoncom.PumpWaitingMessages()


def _is_busy(error: Exception) -> bool:
    hresult = getattr(error, "hresult", None)
    if hresult is None and error.args:
        hresult = error.args[0]
    return isinstance(hresult, int) and hresult in _BUSY_HRESULTS


def _error_tuple(value: Any) -> AoResponseTup:
    while isinstance(value, (tuple, list)) and len(value) == 1:
        value = value[0]
    if value is None or value == "":
        return None, None
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) >= 2:
            return str(value[0]) if value[0] is not None else None, str(value[1])
    return str(value), None


def _error_is_clear(value: Any) -> bool:
    code, message = _error_tuple(value)
    return code in (None, "", "0", "0.0") and message in (None, "", "None")


def _macro_probe(excel: Any, deadline: Deadline) -> None:
    while True:
        deadline.check("AO macro readiness")
        try:
            excel.Run(str(AoMacro.GET_PROPERTY), str(AoProp.LAST_ERROR))
        except Exception as error:
            if not _is_busy(error):
                raise ConnectionBindingError("Configured AO add-in macros are unavailable") from None
            deadline.pause()
        else:
            deadline.check("AO macro readiness")
            return


def ensure_sap_ao_ready(
    excel: Any,
    *,
    timeout_seconds: float = 90,
    poll_seconds: float = 1,
    addin_name: str = COM_ADD_IN_NAME,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    pump: Callable[[], None] = _pump_messages,
) -> None:
    """Probe only the exact configured add-in in a borrowed Excel instance."""
    deadline = Deadline(
        validate_duration(timeout_seconds, "timeout_seconds"),
        clock=clock, sleep=sleep, pump=pump,
        poll_seconds=validate_duration(poll_seconds, "poll_seconds"),
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
    _macro_probe(excel, deadline)


class Controller(ControllerBase):
    def __init__(
        self,
        options: str | Path | ControllerOptions,
        /,
        *,
        staging_policy: StagingPolicy | str | None = None,
        stage_roots: tuple[Path, ...] | None = None,
        startup_timeout_seconds: float = 90,
        poll_seconds: float = .25,
        session_factory: SessionFactory | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        pump: Callable[[], None] = _pump_messages,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.options = options if isinstance(options, ControllerOptions) else ControllerOptions.from_json(options)
        self._ao_clock = clock
        self._ao_sleep = sleep
        self._ao_pump = pump
        super().__init__(
            staging=self.options.staging,
            cooldown_minutes=self.options.refresh_cooldown_minutes,
            staging_policy=self.options.staging_policy if staging_policy is None else staging_policy,
            stage_roots=self.options.stage_roots if stage_roots is None else stage_roots,
            startup_timeout_seconds=startup_timeout_seconds,
            poll_seconds=poll_seconds,
            session_factory=session_factory,
            clock=clock, sleep=sleep, pump=pump, now=now,
        )

    def __enter__(self) -> Self:
        super().__enter__()
        return self

    def _deadline(self, timeout_seconds: float, poll_seconds: float | None = None) -> Deadline:
        return Deadline(
            validate_duration(timeout_seconds, "timeout_seconds"),
            clock=self._ao_clock, sleep=self._ao_sleep, pump=self._ao_pump,
            poll_seconds=self.poll_seconds if poll_seconds is None else validate_duration(poll_seconds, "poll_seconds"),
        )

    def _on_enter(self, deadline: Deadline) -> None:
        self._connect_com_addin()
        self.wait_for_idle(deadline)
        _macro_probe(self.session.excel, deadline)

    def _on_exit(self) -> None:
        pass

    def _connect_com_addin(self) -> None:
        try:
            addin = self.session.get_com_addin(self.options.addin_name)
            if not bool(addin.Connect):
                addin.Connect = True
            if not bool(addin.Connect):
                raise ConnectionBindingError("Configured AO add-in is not connected")
        except WorkbookControllerError:
            raise
        except Exception:
            raise ConnectionBindingError("Cannot connect configured AO add-in") from None

    def _xl_run(self, macro: str | AoMacro, *args: Any, _deadline: Deadline | None = None) -> Any:
        if _deadline is not None:
            _deadline.check("AO macro")
        self._ao_pump()
        try:
            result = self.session.excel.Run(str(macro), *args)
        except Exception as error:
            if self.is_fatal(error):
                self.invalidate(error)
            # COM exception text can echo prompt values. Never include it here.
            if _is_busy(error):
                raise
            raise AoCommandError(f"AO macro {macro} failed") from None
        if _deadline is not None:
            _deadline.check("AO macro")
        return result

    def _checked(
        self, macro: str | AoMacro, *args: Any,
        deadline: Deadline,
        responses: list[tuple[str, int]] | None = None,
    ) -> int:
        while True:
            try:
                result = self._xl_run(macro, *args, _deadline=deadline)
                break
            except Exception as error:
                if not _is_busy(error):
                    raise
                deadline.pause()
        if isinstance(result, bool) or not isinstance(result, (int, float)) or result != AoResponseCode.SUCCESS:
            raise AoCommandError(f"AO macro {macro} rejected the operation")
        if responses is not None:
            label = str(args[0]) if macro == AoMacro.EXEC_CMD else str(macro)
            responses.append((label, int(result)))
        return int(result)

    def _exec_cmd(self, cmd: str | AoCmd, *args: Any) -> int:
        return self._checked(AoMacro.EXEC_CMD, str(cmd), *args, deadline=self._deadline(30))

    def _get_property(self, prop: str | AoProp, *args: Any, deadline: Deadline | None = None) -> Any:
        return self._xl_run(AoMacro.GET_PROPERTY, str(prop), *args, _deadline=deadline)

    @property
    def last_error(self) -> Any:
        return self._get_property(AoProp.LAST_ERROR)

    def get_last_error(self) -> Any:
        try:
            return self.last_error
        except Exception:
            return (None, "<AO LastError unavailable>")

    def _last_error_tuple(self) -> AoResponseTup:
        return _error_tuple(self.get_last_error())

    @property
    def changed_datasources(self) -> Any:
        return self._get_property(AoProp.CHANGED_DATASOURCES)

    @property
    def changed_crosstabs(self) -> Any:
        return self._get_property(AoProp.CHANGED_CROSSTABS)

    @property
    def is_auto_refresh_active(self) -> bool:
        return require_ao_bool(self._get_property(AoProp.IS_AUTO_REFRESH), label="IsAutoRefresh")

    @property
    def is_connected(self) -> bool:
        return require_ao_bool(self._get_property(AoProp.IS_CONNECTED), label="IsConnected")

    def is_datasource_active(self, formula_alias: str, /) -> bool:
        return require_ao_bool(self._get_property(AoProp.IS_DATA_SOURCE_ACTIVE, formula_alias), label="IsDataSourceActive")

    def get_crosstab_newline_count(self, crosstab: str = "Crosstab1", /) -> Any:
        return self._get_property(AoProp.NUMBER_OF_NEW_LINES, crosstab)

    def log_datasource_state(self, ds_alias: str = DEFAULT_AO_DATASOURCE, /) -> None:
        # Deliberately omit LastError text: SAP may echo a rejected prompt.
        _LOG.info("AO datasource %s active=%s", ds_alias, self.is_datasource_active(ds_alias))

    def wait_for_ao_ready(self, timeout_seconds: float = 90, poll_seconds: float = 1) -> None:
        deadline = self._deadline(timeout_seconds, poll_seconds)
        self.wait_for_idle(deadline)
        _macro_probe(self.session.excel, deadline)

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
                if _error_is_clear(error):
                    if active and connected:
                        return
                elif _error_tuple(error)[0] not in _UNRESOLVED:
                    raise AoCommandError("AO datasource readiness reported an error")
            except Exception as error:
                if not _is_busy(error):
                    raise
            deadline.pause()

    def _get_workbook_info(self, wb: Any, key: WorkbookProperty | str, /, *, deadline: Deadline | None = None) -> Any:
        if deadline is not None:
            deadline.check("AO workbook property")
        wb.Activate()
        return self._xl_run(AoMacro.GET_WORKBOOK_INFO, str(key), _deadline=deadline)

    def check_workbook_prop(self, wb_source: WorkbookOptions | Any, prop: WorkbookProperty | str) -> Any:
        if isinstance(wb_source, WorkbookOptions):
            with self.operation(wb_source.filepath) as tx:
                self._wait_datasource(wb_source.ds_alias, tx.deadline)
                return self._get_workbook_info(tx.wb, prop, deadline=tx.deadline)
        return self._get_workbook_info(wb_source, prop)

    def get_effective_filters(self, wb_source: WorkbookOptions | Any, /) -> Any:
        if isinstance(wb_source, WorkbookOptions):
            with self.operation(wb_source.filepath) as tx:
                self._wait_datasource(wb_source.ds_alias, tx.deadline)
                tx.wb.Activate()
                return self._xl_run(AoMacro.LIST_EFFECTIVE_FILTERS, _deadline=tx.deadline)
        wb_source.Activate()
        return self._xl_run(AoMacro.LIST_EFFECTIVE_FILTERS)

    def _timestamp(self, wb: Any, deadline: Deadline | None = None) -> datetime | None:
        value = self._get_workbook_info(wb, WorkbookProperty.LAST_REFRESHED_AT, deadline=deadline)
        return parse_refresh_timestamp(value, date1904=bool(wb.Date1904))

    def get_last_refreshed_at(self, target: WorkbookOptions | Any, /) -> datetime | None:
        if isinstance(target, WorkbookOptions):
            with self.operation(target.filepath) as tx:
                self._wait_datasource(target.ds_alias, tx.deadline)
                return self._timestamp(tx.wb, tx.deadline)
        return self._timestamp(target)

    def set_variable(
        self, key: str, value: Any, /,
        ds_alias: str = DEFAULT_AO_DATASOURCE,
        value_fmt: str = "",
        timeout_seconds: float = 20,
        poll_seconds: float = 1,
        *,
        resolve_prompts: bool = True,
        _deadline: Deadline | None = None,
        _responses: list[tuple[str, int]] | None = None,
    ) -> int:
        if not isinstance(resolve_prompts, bool):
            raise AoCommandError("resolve_prompts must be boolean")
        resolved = _field.resolve_field_dict({key: value})[key] if resolve_prompts else value
        deadline = _deadline if _deadline is not None else self._deadline(timeout_seconds, poll_seconds)
        while True:
            deadline.check("AO prompt")
            try:
                result = self._xl_run(AoMacro.SET_VAR, key, resolved, value_fmt, ds_alias, _deadline=deadline)
                if not isinstance(result, bool) and isinstance(result, (int, float)) and result == AoResponseCode.SUCCESS:
                    if _responses is not None:
                        _responses.append((str(AoMacro.SET_VAR), int(result)))
                    return int(result)
                code, _ = _error_tuple(self._get_property(AoProp.LAST_ERROR, deadline=deadline))
                if code not in _UNRESOLVED:
                    raise AoCommandError("AO rejected a prompt; values and SAP error text redacted")
            except Exception as error:
                if not _is_busy(error):
                    raise
            deadline.pause()

    def clear_variable(
        self, key: str, /, ds_alias: str = DEFAULT_AO_DATASOURCE,
        timeout_seconds: float = 20, poll_seconds: float = 1,
    ) -> int:
        return self.set_variable(key, "", ds_alias, timeout_seconds=timeout_seconds, poll_seconds=poll_seconds, resolve_prompts=False)

    def _set_refresh_behaviour(self, state: Literal["On", "Off"]) -> int:
        return self._checked(AoMacro.SET_REFRESH, state, deadline=self._deadline(30))

    def _set_pause_variable_submission(self, state: Literal["On", "Off"], /) -> int:
        return self._exec_cmd(AoCmd.PAUSE_VARIABLE_SUBMIT, state)

    def _set_auto_refresh(self, state: Literal["On", "Off"], /, *ds_alias: str) -> int:
        return self._exec_cmd(AoCmd.SET_AUTOREFRESH, state, ";".join(ds_alias))

    def _refresh_status(
        self, status: RefreshActiveStatus, deadline: Deadline,
        responses: list[tuple[str, int]] | None = None,
    ) -> None:
        status = RefreshActiveStatus(status)
        refresh, pause = ("On", "Off") if status == RefreshActiveStatus.ACTIVE else ("Off", "On")
        self._checked(AoMacro.SET_REFRESH, refresh, deadline=deadline, responses=responses)
        self._checked(AoMacro.EXEC_CMD, str(AoCmd.PAUSE_VARIABLE_SUBMIT), pause, deadline=deadline, responses=responses)

    def _restore_refresh(self, deadline: Deadline) -> None:
        errors: list[Exception] = []
        for macro, args in (
            (AoMacro.SET_REFRESH, ("On",)),
            (AoMacro.EXEC_CMD, (str(AoCmd.PAUSE_VARIABLE_SUBMIT), "Off")),
        ):
            try:
                self._checked(macro, *args, deadline=deadline)
            except Exception as error:
                errors.append(error)
        if errors:
            self.invalidate(errors[0])
            raise errors[0]

    def set_refresh_active_status(self, status: RefreshActiveStatus, /, sleep: int = 1) -> None:
        deadline = self._deadline(30)
        self._refresh_status(status, deadline)
        if sleep:
            deadline.pause(validate_duration(sleep, "sleep", allow_zero=True))

    def refresh_data(self) -> int:
        return self._exec_cmd(AoCmd.REFRESH_DATA)

    def open_server_workbook(self, name: str, /) -> int:
        return self._checked(AoMacro.OPEN_WORKBOOK, name, deadline=self._deadline(30))

    def _wait_completion(self, wb: Any, ds_alias: str, baseline: datetime | None, deadline: Deadline) -> datetime:
        while True:
            self._wait_datasource(ds_alias, deadline)
            try:
                observed = self._timestamp(wb, deadline)
                if observed is not None and (baseline is None or observed > baseline):
                    # Check again after reading metadata; a timestamp alone is insufficient.
                    self.wait_for_idle(deadline)
                    if not _error_is_clear(self._get_property(AoProp.LAST_ERROR, deadline=deadline)):
                        raise AoCommandError("AO completion reported an error")
                    return observed
            except Exception as error:
                if not _is_busy(error):
                    raise
            deadline.pause()

    def refresh(
        self, fo: WorkbookOptions, /, set_prompts: bool | None = None,
        timeout_minutes: float = 30, force: bool = False, *,
        resolve_prompts: bool = True,
    ) -> RefreshOutcome[AoRefreshDetails]:
        WorkbookOptions.validate_instance(fo)
        if not isinstance(force, bool) or not isinstance(resolve_prompts, bool):
            raise AoCommandError("force and resolve_prompts must be boolean")
        apply_prompts = fo.set_prompts if set_prompts is None else set_prompts
        if not isinstance(apply_prompts, bool):
            raise AoCommandError("set_prompts must be boolean")
        with self.operation(fo.filepath, timeout_minutes=timeout_minutes) as tx:
            tx.phase = "AO datasource readiness"
            tx.wb.Activate()
            self._wait_datasource(fo.ds_alias, tx.deadline)
            previous = self._timestamp(tx.wb, tx.deadline)
            tx.last_timestamp = previous
            remaining = cooldown_remaining(previous, self._now(), self.cooldown_minutes, force=force)
            if remaining > 0:
                return tx.outcome(
                    RefreshStatus.SKIPPED_COOLDOWN, previous, previous,
                    AoRefreshDetails(fo.ds_alias), skip_reason="cooldown",
                    cooldown_remaining_seconds=remaining,
                )
            prompts: Mapping[str, Any] = fo.prompts if apply_prompts else {}
            resolved = _field.resolve_field_dict(prompts) if resolve_prompts and prompts else dict(prompts)
            responses: list[tuple[str, int]] = []
            tx.phase = "AO initial refresh"
            self._checked(AoMacro.EXEC_CMD, str(AoCmd.REFRESH_DATA), deadline=tx.deadline, responses=responses)
            initial = self._wait_completion(tx.wb, fo.ds_alias, previous, tx.deadline)
            tx.last_timestamp = initial
            restoration_needed = True
            original_error: BaseException | None = None
            try:
                tx.phase = "AO pausing prompts"
                self._refresh_status(RefreshActiveStatus.INACTIVE, tx.deadline, responses)
                tx.phase = "AO prompts"
                for key, value in resolved.items():
                    self.set_variable(
                        key, value, fo.ds_alias, resolve_prompts=False,
                        _deadline=tx.deadline, _responses=responses,
                    )
                tx.phase = "AO resuming prompts"
                self._refresh_status(RefreshActiveStatus.ACTIVE, tx.deadline, responses)
                restoration_needed = False
                self._wait_datasource(fo.ds_alias, tx.deadline)
                baseline = self._timestamp(tx.wb, tx.deadline)
                if baseline is None or baseline < initial:
                    raise AoCommandError("AO refresh timestamp regressed before final refresh")
                tx.phase = "AO final refresh"
                self._checked(AoMacro.EXEC_CMD, str(AoCmd.REFRESH_DATA), deadline=tx.deadline, responses=responses)
                refreshed = self._wait_completion(tx.wb, fo.ds_alias, baseline, tx.deadline)
                tx.last_timestamp = refreshed
            except BaseException as error:
                original_error = error
                raise
            finally:
                if restoration_needed:
                    try:
                        # Do not silently extend an exhausted operation deadline.
                        self._restore_refresh(tx.deadline)
                    except Exception as restoration_error:
                        self.invalidate(restoration_error)
                        if original_error is None:
                            raise
            tx.phase = "AO publication"
            tx.commit()
            return tx.outcome(
                RefreshStatus.REFRESHED, previous, refreshed,
                AoRefreshDetails(fo.ds_alias, tuple(resolved), tuple(responses), completion_verified=True),
            )

    def refresh_workbook(
        self, fo: WorkbookOptions, /, set_prompts: bool = False,
        timeout_minutes: float = 30, force: bool = False, *,
        resolve_prompts: bool = True,
    ) -> None:
        """Legacy adapter: second positional prompt flag and None return retained."""
        self.refresh(fo, set_prompts, timeout_minutes, force, resolve_prompts=resolve_prompts)
        return None


__all__ = [
    "Controller", "AoRefreshDetails", "AoCommandError", "ExcelComValueError",
    "is_excel_error_value", "require_ao_bool", "ensure_sap_ao_ready",
]
