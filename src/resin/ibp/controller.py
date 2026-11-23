"""
*`@file`* `ibp/controller`
"""
from __future__ import annotations as _annotations
from dataclasses import dataclass
from typing import Any, Callable, Generator, Self, Sequence, TypeVar
from uuid import uuid4
import shutil, threading, time
import sys
from contextlib import contextmanager
import win32com.client as win32
from pywintypes import com_error
from datetime import datetime, timedelta
from pathlib import Path
from lute import (LogMsg, get_logger, annotate)
from pyqi import (
    Json,
    fs, dt, export,
    safe, guard, require
)
from noxl.engines.xlcom.session import ExcelSession
from noxl.engines.xlcom.workbook import ManagedName

from resin._workbook.transaction import WorkbookTransaction
from resin._workbook.types import PublicationDisposition
from resin.utils import winauto, runtime
from resin._workbook import (
    ConnectionBindingError, ConfigurationError, BaseController, Deadline,
    RefreshOutcome, RefreshStatus, SessionFactory,
    cooldown_remaining, parse_refresh_timestamp
)
from .warning_watcher import version_warning_watcher
from .types import (ConnectionMode, WorkbookProperty)
from .binding import (
    BindingState, 
    BindingObservation, 
    BindingVerifier, 
    naive_binding_verifier
)
from .constants import (VERSION_WARNING_WINDOW_TITLE)
from .global_configuration import (GlobalConfiguration, GlobalConfigurationDict)
from .connection_options import (ConnectionOptions, ConnectionIdentity, ConnectionOptionsDict)
from .workbook_options import (WorkbookOptions)
from .refresh_ui import (RefreshUI, RibbonRefreshUI)
from ._options import (ControllerOptions, ControllerOptionsDict)

mlog = get_logger(__file__, name_depth=1)

EXCEL_UI_LOCK = threading.RLock()
_EXCEL_OBJECT_ERROR = -2146827284
T = TypeVar("T")


@dataclass(frozen=True)
class RefreshDetails():
    requested_connection: ConnectionIdentity
    observed_connection: ConnectionIdentity | None
    connect_called: bool
    binding_reused: bool | None = None


class Controller(BaseController):
    """
    *`@extends`* `BaseController`
    """
    options: ControllerOptions
    connection_options: ConnectionOptions
    api_config: GlobalConfiguration
    ui: RefreshUI
    warning_options: winauto.WindowOptionsDict
    backend: winauto.DesktopBackend | None
    """ not used currently """
    session_factory: SessionFactory | None
    # _ui: RefreshUI | None
    _session: ExcelSession | None
    _ibp: win32.CDispatch | None
    _anchor: win32.CDispatch | None
    _anchor_path: Path | None
    _verifier: BindingVerifier | None
    _identity: ConnectionIdentity
    def __init__(
        self,
        options: ControllerOptions | Json.ObjectSource[ControllerOptionsDict],
        connection_options: ConnectionOptions | Json.ObjectSource[ConnectionOptionsDict],
        api_config: GlobalConfiguration | Json.ObjectSource[GlobalConfigurationDict] | None=None,
        binding_verifier: BindingVerifier | None = naive_binding_verifier,
        ui: RefreshUI | None = None,
        backend: winauto.DesktopBackend | None = None,
        warning_options: winauto.WindowOptionsDict | None=None,
        session_factory: SessionFactory | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        pump: Callable[[], None] = runtime.pump_waiting_messages,
        now: Callable[[], datetime] = datetime.now,
        *,
        verbose: bool=False,
    ):
        self.options = ControllerOptions.from_any(options)
        self.connection_options = ConnectionOptions.from_any(connection_options)
        self.api_config = (
            GlobalConfiguration.from_any(api_config) 
            if api_config 
            else GlobalConfiguration()
        )
        self.ui = ui or RibbonRefreshUI()
        self.backend = backend
        self.warning_options = (
            warning_options 
            or winauto.WindowOptionsDict(title=VERSION_WARNING_WINDOW_TITLE)
        )
        self.verbose = verbose
        self._verifier = binding_verifier
        self._ibp = None
        self._anchor = None # anchor wb win32.CDispatch
        self._anchor_path = self.options.anchor_seed
        self._identity = ConnectionIdentity.from_options(self.connection_options)
        # self._worksheet_connection_cache = dict()

        super().__init__(
            options=self.options,
            session_factory=session_factory,
            clock=clock, 
            sleep=sleep, 
            pump=pump, 
            now=now,
        )
    def __post_init__(self):
        # ========= verify configuration ======================================
        _ID_PROPS = [
            self.connection_options.planning_area,
            self.connection_options.server_url,
        ]
        if (self.options.connection_mode == ConnectionMode.ANCHOR 
            and (
                self._verifier is None 
                or not self.connection_options.name
            )
        ): 
            raise ConfigurationError(LogMsg(
                "ConnectionMode.ANCHOR requires ConnectionOptions.name and binding_verifier",
                connection_options=self.connection_options,
                binding_verifier=self._verifier
            ))
        if (self._verifier is None
            and not self.connection_options.name
            and any(x is None for x in _ID_PROPS)
        ):
            raise ConfigurationError(LogMsg(
                f"Must provide binding_verifier in constructor when:",
                "connection_options.name is undefined",
                "connection_options.planning_area and/or"
                +" connection_options.server_url is defined"
            ))

        if (self._verifier is not None and all(x is None for x in _ID_PROPS)):
            raise ConfigurationError(LogMsg(
                f"Invalid ConnectionOptions for binding verification",
                f"Must define at least one of planning_area, server_url",
            ))
        # ========= set values ================================================
        
        self.warning_options['process'] = self.session.pid
    
    @property
    def ibp(self) -> Any:
        self.session  # Check lifecycle before exposing a COM proxy.
        if self._ibp is None:
            raise ConnectionBindingError("IBP add-in is unavailable")
        return self._ibp

    
    def __enter__(self) -> Self:
        super().__enter__()
        return self

    def _on_enter(self, deadline: Deadline) -> None:
        addin = self.session.get_com_addin(self.options.addin_name)
        deadline.check("IBP add-in connection")
        if not addin.Connect:
            addin.Connect = True
        self._ibp = addin.Object
        if self._ibp is None:
            raise ConnectionBindingError("IBP add-in returned no automation object")
        self.wait_for_idle(deadline)
        if self.options.connection_mode == ConnectionMode.ANCHOR:
            self._create_anchor(deadline)

    def _on_exit(self) -> None:
        closed = self._anchor is None
        try:
            if self._anchor is not None:
                self.session.close_workbook(self._anchor, save_changes=False)
                closed = True
        finally:
            self._anchor = None
            self._ibp = None
            if closed and self._anchor_path is not None:
                try:
                    self._anchor_path.unlink(missing_ok=True)
                finally:
                    self._anchor_path = None

    def _create_anchor(self, deadline: Deadline) -> None:
        seed = self.options.anchor_seed
        self._anchor_path = (self.run_directory
            .joinpath(f"ibp-anchor-{uuid4().hex}{seed.suffix if seed else '.xlsm'}")
        )
        deadline.check("anchor creation")
        if seed is not None:
            shutil.copy2(seed, self._anchor_path)
            deadline.check("anchor seed copy")
            self._anchor = self.session.open_workbook(self._anchor_path)
            deadline.check("anchor open")
            ws = self._anchor.Worksheets(self.options.anchor_sheetname)
        else:
            self._anchor = self.session.add_workbook(self._anchor_path)
            deadline.check("anchor creation")
            ws = self._anchor.Worksheets(1)
        with self._ui_lock(deadline):
            self._anchor.Activate()
            ws.Activate()
            self.wait_for_idle(deadline)
            self._ensure_binding(self._anchor, ws, deadline, force_connect=True)
    
    def _get_active_connection(self, ws: win32.CDispatch, /) -> str | None:
        try:
            return self.ibp.GetActiveConnection(ws)
        except Exception:
            return None

    def _get_worksheet_connections(self, ws: win32.CDispatch, /) -> Any:
        return self.ibp.GetConnections(ws)
    
    def _ensure_binding(
        self, 
        wb: win32.CDispatch, 
        ws: win32.CDispatch, 
        deadline: Deadline, 
        *, 
        force_connect: bool = False,
    ) -> tuple[ConnectionIdentity, ConnectionIdentity, bool]:
        """
        *`@returns`* 
        `(requested, observed, connected) = tuple[ConnectionIdentity, ConnectionIdentity, bool]`
        - `connected (bool)` - whether `self.ibp.Connect(<connection_name>)` was called
        """
        deadline.check("connection verification")
        requested = self._requested(wb)
        if self._verifier is not None:
            observation = self._observe(wb, ws, requested)
            if observation.state == BindingState.VALID and not force_connect:
                assert observation.identity is not None
                self._identity = observation.identity
                return requested, observation.identity, False
        deadline.check("IBP Connect")
        with version_warning_watcher(self.warning_options):
            self.ibp.Connect(requested.name)
        deadline.check("IBP Connect completion")
        self.wait_for_idle(deadline)
        observation = self._observe(wb, ws, requested)
        deadline.check("post-Connect verification")
        if (observation.state != BindingState.VALID 
            or observation.identity is None
        ):
            raise ConnectionBindingError("IBP binding is not usable after one Connect attempt")
        self._identity = observation.identity
        return requested, observation.identity, True

    def _observe(
        self, 
        wb: win32.CDispatch, 
        ws: win32.CDispatch, 
        requested: ConnectionIdentity, 
    ) -> BindingObservation:
        _active_conn = self._get_active_connection(ws)
        if self._verifier is None:
            # Without installed-version proof, never reuse or interpret GetConnections.
            _observed_name = self.get_connection_name(wb)
            if (_observed_name is not None):
                if (not _active_conn):
                    return BindingObservation(BindingState.EXPIRED, requested)
                if (_observed_name != requested.name):
                    raise ConnectionBindingError(LogMsg(
                        "Connect did not establish the requested workbook connection",
                        requested_name=annotate(requested.name),
                        observed_name=annotate(_observed_name),
                        active_connection=_active_conn
                    ))
                return BindingObservation(BindingState.VALID, requested)
            return BindingObservation(BindingState.MISSING, requested)
        try:
            observation = self._verifier(
                requested, 
                _active_conn, 
                workbook=wb, 
                worksheet=ws
            )
        except Exception as e:
            raise ConnectionBindingError(
                "Installed IBP binding verification failed"
            ) from e
        if (not isinstance(observation, BindingObservation) 
            or not isinstance(observation.state, BindingState)
        ):
            raise ConnectionBindingError(
                "binding verifier returned an invalid observation"
                )
        identity = observation.identity
        if identity is not None:
            if (not isinstance(identity, ConnectionIdentity) 
                or not guard.is_non_empty_string(identity.name)
            ):
                raise ConnectionBindingError("binding verifier returned an invalid identity")
            for key in ("name", "planning_area", "server_url"):
                expected = getattr(requested, key)
                actual: str | None = getattr(identity, key)
                if (actual is not None and not guard.is_non_empty_string(actual)):
                    raise ConnectionBindingError(
                        f"binding verifier returned an invalid value for identity field '{key}'"
                    )
                if (expected is not None and actual != expected):
                    raise ConnectionBindingError(
                        "observed binding conflicts with controller identity"
                        )
        if (observation.state == BindingState.VALID and identity is None):
            raise ConnectionBindingError("valid binding observation requires a verified identity")
        return observation


    @contextmanager
    def _ui_lock(self, deadline: Deadline) -> Generator[None]:
        if not EXCEL_UI_LOCK.acquire(timeout=deadline.remaining()):
            deadline.check("waiting for Excel UI lock")
            raise ConnectionBindingError("Excel UI lock unavailable")
        try:
            deadline.check("Excel UI lock")
            yield
        finally:
            EXCEL_UI_LOCK.release()

    def _requested(self, wb: win32.CDispatch) -> ConnectionIdentity:
        name = self.get_connection_name(wb)
        if self._identity is None:
            if not name:
                raise ConnectionBindingError("target has no connection name; configure one explicitly")
            self._identity = ConnectionIdentity(name)
        if name and name != self._identity.name:
            raise ConnectionBindingError("target connection name conflicts with controller identity")
        return self._identity

    def get_workbook_property(
        self, 
        wb: win32.CDispatch | WorkbookOptions, 
        prop: WorkbookProperty | str, 
        /,
        format_value: Callable[[Any], T] = WorkbookProperty.default_formatter
    ) -> T:
        with self._property_workbook(wb) as opened:
            name = ManagedName.entry(opened, str(prop))
            try:
                value = name.RefersToRange.Value
            except com_error as e:
                hresult = getattr(e, "hresult")
                excepinfo = getattr(e, "excepinfo")
                # Scalar defined names raise Excel error 1004 for RefersToRange.
                if (hresult != _EXCEL_OBJECT_ERROR 
                    and (
                        not excepinfo 
                        or (isinstance(excepinfo, Sequence)
                            and len(excepinfo) >= 6
                            and excepinfo[5] != _EXCEL_OBJECT_ERROR
                        )
                    )
                ): 
                    raise
                value = name.Value
            return format_value(value)

    @contextmanager
    def _property_workbook(self, wb: win32.CDispatch | WorkbookOptions) -> Generator[win32.CDispatch]:
        """
        context manager for reading properties of/in workbook com object
        """
        if isinstance(wb, (WorkbookOptions, str, Path)):
            path = wb.path if isinstance(wb, WorkbookOptions) else fs.to_path(wb)
            with self.operation(path) as txn:
                self.wait_for_idle(txn.deadline)
                yield txn.wb
        else:
            self.session
            yield wb
    
    def get_connection_name(self, wb: win32.CDispatch, /) -> str | None:
        value: Any = None
        try: value = self.get_workbook_property(wb, WorkbookProperty.CONNECTION_NAME)
        except Exception: return None
        
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ConnectionBindingError(LogMsg(
                "workbook connection name must be a scalar string"
            ))
        return value
    
    def _timestamp(self, wb: win32.CDispatch, /) -> datetime | None:
        return parse_refresh_timestamp(
            self.get_workbook_property(wb, WorkbookProperty.REFRESH_TIMESTAMP),
            use_1904_epoch=bool(wb.Date1904),
        )


    def get_last_refreshed_at(self, wb: win32.CDispatch, /) -> datetime | None:
        with self._property_workbook(wb) as opened:
            return self._timestamp(opened)
    
    def _wait_timestamp(self, txn: WorkbookTransaction, previous: datetime | None) -> datetime:
        observed: datetime | None = None
        changed_at: float | None = None
        while True:
            txn.deadline.check("IBP refresh completion")
            self.wait_for_idle(txn.deadline)
            current = self._timestamp(txn.wb)
            txn.last_timestamp = current
            if current is not None and (previous is None or current > previous):
                if current != observed:
                    mlog.debug(LogMsg(
                        "Observed advanced IBP refresh timestamp",
                        previous_timestamp=previous,
                        current_timestamp=current,
                    ))
                    observed, changed_at = current, txn.deadline.clock()
                if (changed_at is not None 
                    and txn.deadline.clock() - changed_at >= self.options.stable_seconds
                    ):
                    return current
            else:
                observed, changed_at = None, None
            txn.deadline.pause()


    def refresh(
        self,
        workbook: WorkbookOptions | fs.StrPath,
        /,
        *,
        timeout_minutes: float = 30,
        force: bool=False
    ) -> RefreshOutcome[RefreshDetails]:
        """
        *`@returns`* `outcome (RefreshOutcome[RefreshDetails]) (class)`
        ```
        status: RefreshStatus
        path: Path # updated data workbook is here
        operation_id: str
        started_at: datetime
        ended_at: datetime
        elapsed_seconds: float
        last_refreshed_at: datetime | None
        refreshed_at: datetime | None
        publication: PublicationDisposition
        details: RefreshDetails
        skip_reason: str | None = None
        cooldown_remaining_seconds: float = 0.0
        message: str | LogMsg | None = None
        ```
        """
        wbo = (
            workbook if isinstance(workbook, WorkbookOptions) 
            else WorkbookOptions(fs.to_path(workbook))
        )
        with self.operation(
            wbo.path, 
            timeout_minutes=timeout_minutes, 
        ) as txn:
            with self._ui_lock(txn.deadline):
                txn.set_phase("Check IBP metadata before refresh")
                self.wait_for_idle(txn.deadline)
                txn.wb.Activate()
                ws = txn.wb.Worksheets(wbo.sheetname)
                ws.Activate()
                previous = self._timestamp(txn.wb)
                txn.last_timestamp = previous
                requested = self._requested(txn.wb)
                now_dt = self._now()
                remaining = cooldown_remaining(
                    previous, 
                    now_dt, 
                    self.options.cooldown_seconds, 
                    force=force
                )
                if remaining > 0:
                    return txn.outcome(
                        RefreshStatus.SKIPPED_COOLDOWN, 
                        last_refreshed_at=previous, 
                        refreshed_at=previous,
                        details=RefreshDetails(
                            requested_connection=requested, 
                            observed_connection=None, 
                            connect_called=False, 
                            binding_reused=None
                        ),
                        skip_reason="positive remaining cooldown",
                        cooldown_remaining_seconds=remaining,
                        message=LogMsg(
                            f"Refresh attempted within cooldown period and {force=}.",
                            attempted_at=now_dt.isoformat(),
                            last_refreshed_at=(
                                previous.isoformat() 
                                if previous is not None 
                                else "<unavailable>"
                            ),
                            remaining=dt.seconds_to.minsecstr(remaining)
                        )
                    )
                txn.set_phase("Make IBP Connection")
                requested, observed, connected =self._ensure_binding(
                    txn.wb, 
                    ws, 
                    txn.deadline
                )
                txn.wb.Activate()
                ws.Activate()
                self.wait_for_idle(txn.deadline)
                
                self.wait_for_idle(txn.deadline)
                baseline = self._timestamp(txn.wb)
                txn.last_timestamp = baseline
                completion_baseline = max(
                    (value for value in (previous, baseline) if value is not None),
                    default=None,
                )
                txn.set_phase("IBP refresh dispatch")
                txn.deadline.check(txn.phase)
                refreshed_at: datetime
                try:
                    if (self.api_config.refresh_enabled):
                        self.ibp.Refresh()
                    else:
                        self.ui.refresh(
                            workbook=txn.wb, 
                            worksheet=ws, 
                            pid=self.session.pid,
                            deadline=txn.deadline,
                        )
                    mlog.debug(LogMsg(
                        "IBP refresh dispatch returned; waiting for completion",
                        baseline_timestamp=completion_baseline,
                    ))
                    txn.set_phase("IBP refresh completion")
                    refreshed_at = self._wait_timestamp(txn, completion_baseline)
                except BaseException as e:
                    self.invalidate(e)
                    raise
            txn.commit() # handles publication disposition
            _cooldown_delta = timedelta(seconds=self.options.cooldown_seconds)
            return txn.outcome(
                RefreshStatus.REFRESHED,
                last_refreshed_at=previous, 
                refreshed_at=refreshed_at,
                details=RefreshDetails(
                    requested, 
                    observed, 
                    connected, 
                    not connected, 
                ),
                cooldown_remaining_seconds=self.options.cooldown_seconds,
                message=LogMsg(
                    "Successfully refreshed IBP workbook",
                    workbook=wbo.path.name,
                    refreshed_at=refreshed_at.isoformat(),
                    last_refreshed_at=(
                        previous.isoformat() 
                        if previous is not None 
                        else "<unavailable>"
                    ),
                    next_refresh_available_at=(
                        refreshed_at + _cooldown_delta
                    ).isoformat(),
                    time_until_next_refresh_available=dt.seconds_to.minsecstr(
                        ((refreshed_at+_cooldown_delta) - dt.now()).total_seconds()
                    )
                ),
                
            )

__all__ = export(Controller, RefreshDetails)