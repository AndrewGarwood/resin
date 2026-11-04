"""IBP refresh controller.

Workbook mode is the default. Anchor mode is experimental and requires an
installed-version binding verifier; no GetConnections/authentication shape is
assumed. UI automation requires exclusive desktop access. Filters and writeback
are unsupported. Timestamps retain Excel's local-naive interpretation.
"""
from __future__ import annotations

import shutil
import threading
import time
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol
from uuid import uuid4

import pythoncom

from .._workbook import (
    ConfigurationError, ConnectionBindingError, ControllerBase, Deadline,
    RefreshOutcome, RefreshStatus, SessionFactory, StagingPolicy,
    cooldown_remaining, parse_refresh_timestamp, read_workbook_name,
    validate_duration,
)
from pyqi import BaseStrEnum
from ..utils import winauto
from .constants import (
    ConnectionMode, IBP_COM_ADDIN_NAME, IBP_RIBBON_TITLE, RefreshMethod, WorkbookProperty,
)
from ._options import ControllerOptions, RefreshInfo, WorkbookOptions

EXCEL_UI_LOCK = threading.RLock()


@dataclass(frozen=True)
class ConnectionIdentity:
    name: str
    planning_area: str | None = None
    server_url: str | None = None
    id: str | None = None


class BindingState(BaseStrEnum):
    VALID = "valid"
    MISSING = "missing"
    EXPIRED = "expired"


@dataclass(frozen=True)
class BindingObservation:
    """VALID means the verifier proved identity AND usable authentication."""
    state: BindingState
    identity: ConnectionIdentity | None = None


class BindingVerifier(Protocol):
    def __call__(
        self, *, workbook: Any, worksheet: Any, requested: ConnectionIdentity,
        connections: Any, connect_result: Any,
    ) -> BindingObservation:
        """Validate installed API shapes; never return VALID from metadata alone."""
        ...


class RefreshUI(Protocol):
    def refresh(
        self, *, workbook: Any, worksheet: Any, pid: int, path: Path,
        backend: winauto.DesktopBackend, deadline: Deadline,
    ) -> None: ...


class RibbonRefreshUI:
    """Use existing PID/window and unique-control selectors, scoped to Ribbon."""
    def __init__(self, ribbon_title: str = "Ribbon") -> None:
        self.ribbon_title = ribbon_title

    def refresh(
        self, *, workbook: Any, worksheet: Any, pid: int, path: Path,
        backend: winauto.DesktopBackend, deadline: Deadline,
    ) -> None:
        deadline.check("UI activation")
        workbook.Activate()
        worksheet.Activate()
        _, window = winauto.attach_to_process_window(
            pid, path.name, backend=backend, require_unique=True,
            ignore_case=True, timeout_seconds=deadline.remaining(),
        )
        deadline.check("ribbon selection")
        window.set_focus()
        ribbon = winauto.find_available_control(
            window, title=self.ribbon_title,
            ctrl_types=(winauto.UiaControl.PANE, winauto.UiaControl.TOOL_BAR),
            require_unique=True,
        )
        tab = winauto.find_available_control(
            ribbon, title=IBP_RIBBON_TITLE,
            ctrl_types=(winauto.UiaControl.TAB_ITEM,), require_unique=True,
        )
        deadline.check("IBP tab selection")
        tab.click_input()
        button = winauto.find_available_control(
            ribbon, title="Refresh",
            ctrl_types=(winauto.CommonControl.BUTTON,), require_unique=True,
        )
        deadline.check("IBP refresh dispatch")
        button.click_input()


@dataclass(frozen=True)
class RefreshDetails:
    requested_connection: ConnectionIdentity
    observed_connection: ConnectionIdentity | None
    method: RefreshMethod
    binding_reused: bool | None
    connect_called: bool


class Controller(ControllerBase):
    """Own one connection identity and one Excel session.

    Without a verifier, workbook compatibility mode requires Connect to return
    True/integer 1 and matching workbook name metadata. It never assumes an
    existing authenticated binding is reusable. Other connection identity
    fields require a verifier. These return shapes are not live-certified.

    Anchor mode authenticates eagerly, even if every later target is skipped.
    Configure anchor_seed explicitly if the installed add-in needs a template;
    unsupported blank creation never silently falls back to another workbook.
    """
    def __init__(
        self, options: str | Path | ControllerOptions, /,
        backend: winauto.DesktopBackend = winauto.DesktopBackend.UIA, *,
        binding_verifier: BindingVerifier | None = None,
        ui: RefreshUI | None = None,
        stable_seconds: float = 2,
        staging_policy: StagingPolicy | str | None = None,
        stage_roots: tuple[Path, ...] | None = None,
        startup_timeout_seconds: float = 90,
        poll_seconds: float = .25,
        session_factory: SessionFactory | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        pump: Callable[[], object] = pythoncom.PumpWaitingMessages,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.options = options if isinstance(options, ControllerOptions) else ControllerOptions.from_json(options)
        self.conn = self.options.conn
        try:
            self.backend = winauto.DesktopBackend(backend)
        except ValueError as exc:
            raise ConfigurationError("unsupported IBP UI backend") from exc
        self.stable_seconds = validate_duration(stable_seconds, "stable_seconds")
        self._verifier = binding_verifier
        if binding_verifier is not None and not callable(binding_verifier):
            raise ConfigurationError("binding_verifier must be callable")
        if self.options.connection_mode == ConnectionMode.ANCHOR:
            if binding_verifier is None or self.conn.name is None:
                raise ConfigurationError("experimental anchor mode requires a name and explicit binding_verifier")
        if binding_verifier is None and any(
            value is not None for value in (self.conn.planning_area, self.conn.server_url, self.conn.id)
        ):
            raise ConfigurationError("non-name connection identity requires an explicit binding_verifier")
        self._ui = ui if ui is not None else RibbonRefreshUI()
        self._ibp: Any = None
        self._anchor: Any = None
        self._anchor_path: Path | None = None
        self._identity: ConnectionIdentity | None = (
            ConnectionIdentity(self.conn.name, self.conn.planning_area, self.conn.server_url, self.conn.id)
            if self.conn.name is not None else None
        )
        super().__init__(
            staging=self.options.staging, cooldown_minutes=self.options.refresh_cooldown_minutes,
            staging_policy=self.options.staging_policy if staging_policy is None else staging_policy,
            stage_roots=self.options.stage_roots if stage_roots is None else stage_roots,
            startup_timeout_seconds=startup_timeout_seconds, poll_seconds=poll_seconds,
            session_factory=session_factory, clock=clock, sleep=sleep, pump=pump, now=now,
        )

    def __enter__(self) -> Controller:
        super().__enter__()
        return self

    @property
    def ibp(self) -> Any:
        self.session  # Check lifecycle before exposing a COM proxy.
        if self._ibp is None:
            raise ConnectionBindingError("IBP add-in is unavailable")
        return self._ibp

    def _on_enter(self, deadline: Deadline) -> None:
        addin = self.session.get_com_addin(IBP_COM_ADDIN_NAME)
        deadline.check("IBP add-in connection")
        if not addin.Connect:
            addin.Connect = True
        self._ibp = addin.Object
        if self._ibp is None:
            raise ConnectionBindingError("IBP add-in returned no automation object")
        self.wait_for_idle(deadline)
        if self.options.connection_mode == ConnectionMode.ANCHOR:
            self._create_anchor(deadline)

    def _create_anchor(self, deadline: Deadline) -> None:
        seed = self.options.anchor_seed
        self._anchor_path = self.run_directory / f"ibp-anchor-{uuid4().hex}{seed.suffix if seed else '.xlsx'}"
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

    @contextmanager
    def _ui_lock(self, deadline: Deadline) -> Iterator[None]:
        if not EXCEL_UI_LOCK.acquire(timeout=deadline.remaining()):
            deadline.check("waiting for Excel UI lock")
            raise ConnectionBindingError("Excel UI lock unavailable")
        try:
            deadline.check("Excel UI lock")
            yield
        finally:
            EXCEL_UI_LOCK.release()

    def _requested(self, wb: Any) -> ConnectionIdentity:
        name = self.get_connection_name(wb)
        if self._identity is None:
            if not name:
                raise ConnectionBindingError("target has no connection name; configure one explicitly")
            self._identity = ConnectionIdentity(name)
        if name and name != self._identity.name:
            raise ConnectionBindingError("target connection name conflicts with controller identity")
        return self._identity

    def _observe(
        self, wb: Any, ws: Any, requested: ConnectionIdentity, connect_result: Any,
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
                workbook=wb, worksheet=ws, requested=requested,
                connections=self.ibp.GetConnections(ws), connect_result=connect_result,
            )
        except Exception as error:
            raise ConnectionBindingError("installed IBP binding verification failed") from error
        if not isinstance(observation, BindingObservation) or not isinstance(observation.state, BindingState):
            raise ConnectionBindingError("binding verifier returned an invalid observation")
        identity = observation.identity
        if identity is not None:
            if not isinstance(identity, ConnectionIdentity) or not isinstance(identity.name, str) or not identity.name:
                raise ConnectionBindingError("binding verifier returned an invalid identity")
            for key in ("name", "planning_area", "server_url", "id"):
                expected = getattr(requested, key)
                actual = getattr(identity, key)
                if actual is not None and (not isinstance(actual, str) or not actual.strip()):
                    raise ConnectionBindingError("binding verifier returned an invalid identity field")
                if expected is not None and actual != expected:
                    raise ConnectionBindingError("observed binding conflicts with controller identity")
        if observation.state == BindingState.VALID and identity is None:
            raise ConnectionBindingError("valid binding observation requires a verified identity")
        return observation

    def _ensure_binding(
        self, wb: Any, ws: Any, deadline: Deadline, *, force_connect: bool = False,
    ) -> tuple[ConnectionIdentity, ConnectionIdentity, bool]:
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
        self.wait_for_idle(deadline)
        observation = self._observe(wb, ws, requested, result)
        deadline.check("post-Connect verification")
        if observation.state != BindingState.VALID or observation.identity is None:
            raise ConnectionBindingError("IBP binding is not usable after one Connect attempt")
        self._identity = observation.identity
        return requested, observation.identity, True

    def _timestamp(self, wb: Any) -> datetime | None:
        return parse_refresh_timestamp(
            read_workbook_name(wb, WorkbookProperty.REFRESH_TIMESTAMP, missing_ok=True),
            date1904=bool(wb.Date1904),
        )

    def _wait_timestamp(self, tx: Any, previous: datetime | None) -> datetime:
        observed: datetime | None = None
        changed_at: float | None = None
        while True:
            tx.deadline.check("IBP refresh completion")
            self.wait_for_idle(tx.deadline)
            current = self._timestamp(tx.wb)
            tx.last_timestamp = current
            if current is not None and (previous is None or current > previous):
                if current != observed:
                    observed, changed_at = current, tx.deadline.clock()
                if changed_at is not None and tx.deadline.clock() - changed_at >= self.stable_seconds:
                    return current
            else:
                observed, changed_at = None, None
            tx.deadline.pause()

    def refresh(
        self, workbook: WorkbookOptions | str | Path, /, *,
        timeout_minutes: float = 30, method: RefreshMethod = RefreshMethod.PYWINAUTO,
        force: bool = False,
    ) -> RefreshOutcome[RefreshDetails]:
        """Refresh once, requiring a stable advanced *actual* workbook timestamp.

        No backend fallback or refresh replay occurs. A single pre-refresh
        Connect is allowed when binding is absent/expired. Blocking COM calls
        cannot be interrupted by the polling deadline.
        """
        wbo = workbook if isinstance(workbook, WorkbookOptions) else WorkbookOptions(Path(workbook))
        if wbo.filters:
            raise ConfigurationError("IBP filter mutation is unsupported")
        try:
            method = RefreshMethod(method)
        except ValueError as exc:
            raise ConfigurationError("unsupported IBP refresh method") from exc
        if not isinstance(force, bool):
            raise ConfigurationError("force must be boolean")
        with self.operation(wbo.path, timeout_minutes=timeout_minutes) as tx:
            # Hold activation through completion: another controller must not steal focus.
            with self._ui_lock(tx.deadline):
                tx.phase = "IBP metadata"
                self.wait_for_idle(tx.deadline)
                tx.wb.Activate()
                ws = tx.wb.Worksheets(wbo.sheetname)
                ws.Activate()
                previous = self._timestamp(tx.wb)
                tx.last_timestamp = previous
                requested = self._requested(tx.wb)
                remaining = cooldown_remaining(previous, self._now(), self.cooldown_minutes, force=force)
                if remaining > 0:
                    return tx.outcome(
                        RefreshStatus.SKIPPED_COOLDOWN, previous, previous,
                        RefreshDetails(requested, None, method, None, False),
                        skip_reason="refresh cooldown", cooldown_remaining_seconds=remaining,
                    )
                tx.phase = "IBP connection"
                requested, observed, connected = self._ensure_binding(tx.wb, ws, tx.deadline)
                tx.wb.Activate()
                ws.Activate()
                self.wait_for_idle(tx.deadline)
                baseline = self._timestamp(tx.wb)
                tx.last_timestamp = baseline
                completion_baseline = max(
                    (value for value in (previous, baseline) if value is not None),
                    default=None,
                )
                tx.phase = "IBP refresh dispatch"
                tx.deadline.check(tx.phase)
                try:
                    if method == RefreshMethod.API:
                        self.ibp.Refresh()
                    else:
                        self._ui.refresh(
                            workbook=tx.wb, worksheet=ws, pid=self.session.pid,
                            path=tx.staged_path, backend=self.backend, deadline=tx.deadline,
                        )
                    tx.phase = "IBP refresh completion"
                    refreshed = self._wait_timestamp(tx, completion_baseline)
                except BaseException as error:
                    # Completion may still be in flight: never reuse uncertain add-in state.
                    self.invalidate(error)
                    raise
            tx.commit()
            return tx.outcome(
                RefreshStatus.REFRESHED, previous, refreshed,
                RefreshDetails(requested, observed, method, not connected, connected),
            )

    def refresh_workbook(
        self, wbo: WorkbookOptions, /, timeout_minutes: float = 30,
        method: RefreshMethod = RefreshMethod.PYWINAUTO,
    ) -> RefreshInfo:
        """Deprecated adapter, retaining legacy placeholder strings on skips."""
        warnings.warn("refresh_workbook is deprecated; use refresh for explicit status", DeprecationWarning, stacklevel=2)
        outcome = self.refresh(wbo, timeout_minutes=timeout_minutes, method=method)
        assert outcome.refreshed_at is not None
        if outcome.status == RefreshStatus.SKIPPED_COOLDOWN:
            return RefreshInfo(outcome.refreshed_at, "<No connection made>", "<No connection made>")
        identity = outcome.details.observed_connection
        assert identity is not None
        return RefreshInfo(outcome.refreshed_at, identity.name, identity.id)

    @contextmanager
    def _property_workbook(self, wb: Any) -> Iterator[Any]:
        if isinstance(wb, (WorkbookOptions, str, Path)):
            path = wb.path if isinstance(wb, WorkbookOptions) else Path(wb)
            with self.operation(path) as tx:
                self.wait_for_idle(tx.deadline)
                yield tx.wb
        else:
            self.session
            yield wb

    def get_workbook_property(
        self, wb: Any, prop: WorkbookProperty | str, /,
        format_value: Callable[[Any], Any] = WorkbookProperty.default_formatter,
    ) -> Any:
        with self._property_workbook(wb) as opened:
            return format_value(read_workbook_name(opened, str(prop), missing_ok=True))

    def get_connection_name(self, wb: Any, /) -> str | None:
        value = self.get_workbook_property(wb, WorkbookProperty.CONNECTION_NAME)
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ConnectionBindingError("workbook connection name must be a scalar string")
        return value

    def get_last_refreshed_at(self, wb: Any, /) -> datetime | None:
        with self._property_workbook(wb) as opened:
            return self._timestamp(opened)

    @contextmanager
    def bind_session(self, session: Any, /) -> Iterator[Controller]:
        raise ConfigurationError("borrowed sessions require a safe ownership agreement and are unsupported")
        yield self
