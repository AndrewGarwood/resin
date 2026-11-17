"""
*`@file`* `ibp/controller`
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Generator, Self, TypeVar
from uuid import uuid4
import shutil, threading, time
from contextlib import contextmanager
import win32com.client as win32
from datetime import datetime, timedelta
from pathlib import Path
from lute import LogMsg
from pyqi import (Json, Array, fs, guard, dt, export)
from noxl.engines.xlcom.session import ExcelSession
from noxl.engines.xlcom.workbook import ManagedName

from resin._workbook.transaction import WorkbookTransaction
from resin._workbook.types import PublicationDisposition
from .constants import (
    VERSION_WARNING_WINDOW_TITLE
)
from .types import (ConnectionMode, WorkbookProperty)
from .binding import (BindingState, BindingObservation, BindingVerifier)
from resin.utils import winauto, runtime
from pywinauto.controls.hwndwrapper import (DialogWrapper)
from resin._workbook import (
    ConnectionBindingError, ConfigurationError, BaseController, Deadline,
    RefreshOutcome, RefreshStatus, SessionFactory,
    cooldown_remaining, parse_refresh_timestamp
)
from .global_configuration import (GlobalConfiguration, GlobalConfigurationDict)
from .connection_options import (ConnectionOptions, ConnectionIdentity, ConnectionOptionsDict)
from .workbook_options import (WorkbookOptions)
from .refresh_ui import (RefreshUI, RibbonRefreshUI)
from ._options import (ControllerOptions, ControllerOptionsDict)

EXCEL_UI_LOCK = threading.RLock()
T = TypeVar("T")


@dataclass(frozen=True)
class RefreshDetails():
    requested_connection: ConnectionIdentity
    observed_connection: ConnectionIdentity | None
    connect_called: bool
    binding_reused: bool | None = None
    publication: PublicationDisposition = PublicationDisposition.NOT_ATTEMPTED


class Controller(BaseController):
    """
    *`@extends`* `BaseController`
    """
    options: ControllerOptions
    connection_options: ConnectionOptions
    api_config: GlobalConfiguration
    ui: RefreshUI
    backend: winauto.DesktopBackend | None
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
        /,
        connection_options: ConnectionOptions | Json.ObjectSource[ConnectionOptionsDict],
        api_config: GlobalConfiguration | Json.ObjectSource[GlobalConfigurationDict],
        binding_verifier: BindingVerifier | None = None,
        ui: RefreshUI | None = None,
        backend: winauto.DesktopBackend | None = None,
        session_factory: SessionFactory | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        pump: Callable[[], None] = runtime.pump_waiting_messages,
        now: Callable[[], datetime] = datetime.now,

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
        self._verifier = binding_verifier
        self._ibp = None
        self._anchor = None # anchor wb win32.CDispatch
        self._anchor_path = None
        self._identity = ConnectionIdentity.from_options(self.connection_options)

        super().__init__(
            options=self.options,
            session_factory=session_factory,
            clock=clock, 
            sleep=sleep, 
            pump=pump, 
            now=now,
        )
    def __post_init__(self):
        if (self.options.connection_mode == ConnectionMode.ANCHOR 
            and (
                self._verifier is None 
                or not self.connection_options.name
            )
        ): 
            raise ConfigurationError(LogMsg(
                "ConnectionMode.ANCHOR requires ConnectionOptions.name and binding_verifier"
            ))
        
        if (self._verifier is None
            and not self.connection_options.name
            and Array.some(
                [
                    self.connection_options.planning_area,
                    self.connection_options.server_url,
                    self.connection_options.connstr
                ],
                lambda x: x is not None
            )
        ):
            raise ConfigurationError(LogMsg(
                f"Must provide binding_verifier in construction if ConnectionOptions.name is undefined"
            ))

    @property
    def ibp(self) -> Any:
        self.session  # Check lifecycle before exposing a COM proxy.
        if self._ibp is None:
            raise ConnectionBindingError("IBP add-in is unavailable")
        return self._ibp

    # @property
    # def ui(self) -> RefreshUI:
    #     if (self._ui is None):
    #         raise RuntimeError(LogMsg(f"self._ui is undefined"))
    #     return self._ui
    
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
            observation = self._observe(wb, ws, requested, None)
            if observation.state == BindingState.VALID and not force_connect:
                assert observation.identity is not None
                self._identity = observation.identity
                return requested, observation.identity, False
        deadline.check("IBP Connect")
        result = self.ibp.Connect(requested.name)
        deadline.check("Closing warning window if exists")
        self._handle_version_warning()
        self.wait_for_idle(deadline)
        observation = self._observe(wb, ws, requested, result)
        deadline.check("post-Connect verification")
        if observation.state != BindingState.VALID or observation.identity is None:
            raise ConnectionBindingError("IBP binding is not usable after one Connect attempt")
        self._identity = observation.identity
        return requested, observation.identity, True

    def _handle_version_warning(
        self, 
        title: str=VERSION_WARNING_WINDOW_TITLE, 
        /,
    ):
        warning_dlg = winauto.window.find(
            title, 
            strict=False, 
            expected_wrapper=DialogWrapper
        )
        if (not warning_dlg): 
            return False
        warning_dlg.close()
        return True
    
    def _observe(
        self, 
        wb: win32.CDispatch, 
        ws: win32.CDispatch, 
        requested: ConnectionIdentity, 
        connect_result: Any,
    ) -> BindingObservation:
        if self._verifier is None:
            # Without installed-version proof, never reuse or interpret GetConnections.
            if type(connect_result) not in (bool, int) or connect_result != 1:
                raise ConnectionBindingError("Connect did not return a verified success value")
            if self.get_connection_name(wb) != requested.name:
                raise ConnectionBindingError("Connect did not establish the requested workbook connection")
            return BindingObservation(BindingState.VALID, requested)
        try:
            observation = self._verifier(
                workbook=wb, 
                worksheet=ws, 
                requested=requested,
                connections=self.ibp.GetConnections(ws), 
                connect_result=connect_result,
            )
        except Exception as e:
            raise ConnectionBindingError(
                "installed IBP binding verification failed"
            ) from e
        if (not isinstance(observation, BindingObservation) 
            or not isinstance(observation.state, BindingState)
        ):
            raise ConnectionBindingError("binding verifier returned an invalid observation")
        identity = observation.identity
        if identity is not None:
            if (not isinstance(identity, ConnectionIdentity) 
                or not guard.is_non_empty_string(identity.name)
            ):
                raise ConnectionBindingError("binding verifier returned an invalid identity")
            for key in ("name", "planning_area", "server_url", "id"):
                expected = getattr(requested, key)
                actual = getattr(identity, key)
                if (actual is not None 
                    and (
                        not isinstance(actual, str) 
                        or not actual.strip()
                        )
                    ):
                    raise ConnectionBindingError("binding verifier returned an invalid identity field")
                if expected is not None and actual != expected:
                    raise ConnectionBindingError("observed binding conflicts with controller identity")
        if observation.state == BindingState.VALID and identity is None:
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
            return format_value(ManagedName.ref_range_value(opened, str(prop)))

    @contextmanager
    def _property_workbook(self, wb: win32.CDispatch | WorkbookOptions) -> Generator[win32.CDispatch]:
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
        try:
            return parse_refresh_timestamp(
                ManagedName.ref_range_value(wb, WorkbookProperty.REFRESH_TIMESTAMP),
                use_1904_epoch=bool(wb.Date1904),
            )
        except Exception:
            return None


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
        wbo = (
            workbook if isinstance(workbook, WorkbookOptions) 
            else WorkbookOptions(fs.to_path(workbook))
        )
        with self.operation(wbo.path, timeout_minutes=timeout_minutes) as txn:
            with self._ui_lock(txn.deadline):
                txn.phase = "IBP metadata"
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
                txn.phase = "IBP Connection"
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
                txn.phase = "IBP refresh dispatch"
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
                            path=txn.staged_path,
                            backend=self.backend,
                            deadline=txn.deadline
                        )
                    txn.phase = "IBP refresh completion"
                    refreshed_at = self._wait_timestamp(txn, completion_baseline)
                except BaseException as e:
                    self.invalidate(e)
                    raise
            dispo = txn.commit()
            return txn.outcome(
                RefreshStatus.REFRESHED,
                last_refreshed_at=previous, 
                refreshed_at=refreshed_at,
                details=RefreshDetails(
                    requested, 
                    observed, 
                    connected, 
                    not connected, 
                    dispo
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
                        refreshed_at 
                        + timedelta(seconds=self.options.cooldown_seconds)
                    ).isoformat()
                )
            )

__all__ = export(Controller, RefreshDetails)