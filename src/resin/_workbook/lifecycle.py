"""Single-threaded, single-use Excel ownership for SAP workbook controllers."""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
from datetime import datetime
from pathlib import Path
import sys
import tempfile
import threading
import time
from typing import Any, Callable, Iterator, TYPE_CHECKING

import pythoncom
from pywintypes import com_error
from lute import get_logger

from .models import (
    ConfigurationError, ControllerState, DeadSessionError, Session, SessionFactory,
    StagingPolicy, WorkbookControllerError, WorkbookIOError, validate_duration,
    validate_workbook_path,
)
from .timing import Deadline

logger = get_logger(__name__)

if TYPE_CHECKING:
    from .transaction import WorkbookTransaction


def default_session_factory() -> Session:
    from noxl.engines.xlcom import ExcelSession
    return ExcelSession(
        visible=True, display_alerts=True, screen_updating=True, enable_events=True,
        kill_on_exit=True,
    )


class ControllerBase:
    def __init__(
        self,
        *,
        staging: Path,
        cooldown_minutes: float = 30,
        staging_policy: StagingPolicy | str = StagingPolicy.ALWAYS,
        stage_roots: tuple[Path, ...] = (),
        startup_timeout_seconds: float = 90,
        poll_seconds: float = 0.25,
        session_factory: SessionFactory | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        pump: Callable[[], object] = pythoncom.PumpWaitingMessages,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        if str(staging).lower().startswith(("http:", "https:", "\\\\")):
            raise ConfigurationError("staging must be a local filesystem directory")
        self.staging = Path(staging).expanduser().resolve()
        self.cooldown_minutes = validate_duration(
            cooldown_minutes, "cooldown_minutes", allow_zero=True
        )
        try:
            self.staging_policy = StagingPolicy(staging_policy)
        except ValueError as error:
            raise ConfigurationError("Invalid staging_policy") from error
        self.stage_roots = tuple(Path(root).resolve() for root in stage_roots)
        self.startup_timeout_seconds = validate_duration(
            startup_timeout_seconds, "startup_timeout_seconds"
        )
        self.poll_seconds = validate_duration(poll_seconds, "poll_seconds")
        self._session_factory = session_factory or default_session_factory
        self._clock, self._sleep, self._pump, self._now = clock, sleep, pump, now
        self._state = ControllerState.NEW
        self._owner_thread: int | None = None
        self._stack: ExitStack | None = None
        self._session: Session | None = None
        self._pid: int | None = None
        self._run_directory: Path | None = None
        self._busy = False
        self._targets: dict[int, Any] = {}
        self._retained: set[Path] = set()

    @property
    def state(self) -> ControllerState:
        return self._state

    def _check_thread(self) -> None:
        if self._owner_thread is not None and self._owner_thread != threading.get_ident():
            raise WorkbookControllerError("Controller used from a different thread")

    @property
    def session(self) -> Session:
        self._check_thread()
        if self._session is None or self._state not in {
            ControllerState.ENTERING, ControllerState.READY, ControllerState.CLOSING
        }:
            raise DeadSessionError("Controller has no usable Excel session")
        return self._session

    @property
    def run_directory(self) -> Path:
        if self._run_directory is None:
            raise WorkbookControllerError("Controller has not been entered")
        return self._run_directory

    def deadline(self, seconds: float) -> Deadline:
        return Deadline(
            seconds, clock=self._clock, sleep=self._sleep, pump=self._pump,
            poll_seconds=self.poll_seconds,
        )

    def __enter__(self) -> ControllerBase:
        self._check_thread()
        if self._state != ControllerState.NEW:
            raise WorkbookControllerError("Controller objects are single-use")
        self._owner_thread = threading.get_ident()
        self._state = ControllerState.ENTERING
        stack = ExitStack()
        self._stack = stack
        try:
            deadline = self.deadline(self.startup_timeout_seconds)
            self.staging.mkdir(parents=True, exist_ok=True)
            self._run_directory = Path(tempfile.mkdtemp(prefix="resin-", dir=self.staging))
            stack.callback(self._cleanup_run_directory)
            self._session = stack.enter_context(self._session_factory())
            self._pid = self._session.pid
            stack.callback(self._cleanup_addin)
            self._on_enter(deadline)
            deadline.check("controller startup")
            self._state = ControllerState.READY
        except BaseException:
            primary = sys.exc_info()
            self._state = ControllerState.CLOSING
            try:
                stack.__exit__(*primary)
            except BaseException:
                logger.exception("Secondary failure unwinding controller startup")
            finally:
                self._session = None
                self._stack = None
                self._state = ControllerState.FAILED
            raise
        return self

    def _on_enter(self, deadline: Deadline) -> None:
        pass

    def _on_exit(self) -> None:
        pass

    def _cleanup_addin(self) -> None:
        self._on_exit()

    def _cleanup_run_directory(self) -> None:
        root = self._run_directory
        if root is None:
            return
        # Transactions remove their own disposable paths. Never sweep a shared tree.
        if not self._retained:
            root.rmdir()
        else:
            logger.warning("Workbook recovery files retained at %s", root)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self._check_thread()
        if self._busy:
            raise WorkbookControllerError("Cannot exit during an active workbook operation")
        stack = self._stack
        if stack is None:
            return False
        failed = self._state == ControllerState.FAILED or exc is not None
        self._state = ControllerState.CLOSING
        try:
            try:
                self._close_targets()
            except Exception:
                if exc is None:
                    raise
                logger.exception("Secondary failure closing target workbooks")
            finally:
                try:
                    stack.__exit__(exc_type, exc, tb)
                except Exception:
                    if exc is None:
                        raise
                    logger.exception("Secondary failure closing Excel controller")
        except BaseException:
            failed = True
            raise
        finally:
            self._session = None
            self._stack = None
            self._state = ControllerState.FAILED if failed else ControllerState.CLOSED
        return False

    def _close_targets(self) -> None:
        errors: list[Exception] = []
        for key, wb in list(self._targets.items())[::-1]:
            try:
                if self._session is not None:
                    self._session.close_workbook(wb, save_changes=False)
            except Exception as error:
                logger.exception("Failed closing controller-owned workbook")
                errors.append(error)
            finally:
                self._targets.pop(key, None)
        if errors:
            raise WorkbookIOError("Failed closing controller-owned workbooks") from errors[0]

    def invalidate(self, error: BaseException) -> None:
        self._state = ControllerState.FAILED
        logger.error("Excel session invalidated (%s)", type(error).__name__)

    @staticmethod
    def is_fatal(error: BaseException) -> bool:
        from noxl.types import ExcelSaveTimeoutError
        fatal_hresult = {-2147417848, -2147023174, -2147220995, -2147023170}
        seen: set[int] = set()
        current: BaseException | None = error
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if isinstance(current, (ExcelSaveTimeoutError, DeadSessionError)):
                return True
            if getattr(current, "hresult", None) in fatal_hresult:
                return True
            current = current.__cause__
        return False

    def wait_for_idle(self, deadline: Deadline) -> None:
        while True:
            deadline.check("Excel readiness")
            deadline.pump()
            try:
                excel = self.session.excel
                if bool(excel.Ready) and int(excel.CalculationState) == 0:
                    return
            except com_error as error:
                if getattr(error, "hresult", None) not in {-2147418111, -2147417846}:
                    raise
            deadline.pause()

    def should_stage(self, path: Path) -> bool:
        if self.staging_policy == StagingPolicy.ALWAYS:
            return True
        if self.staging_policy == StagingPolicy.NEVER:
            return False
        return str(path).startswith("\\\\") or any(
            path.is_relative_to(root) for root in self.stage_roots
        )

    @contextmanager
    def operation(
        self, path: Path, timeout_minutes: float = 30
    ) -> Iterator[WorkbookTransaction]:
        from .transaction import WorkbookTransaction

        self._check_thread()
        if self._state != ControllerState.READY:
            raise DeadSessionError("Refresh requires a READY controller")
        if self._busy:
            raise WorkbookControllerError("Concurrent/reentrant workbook operation rejected")
        deadline = self.deadline(validate_duration(timeout_minutes, "timeout_minutes") * 60)
        source = validate_workbook_path(path)
        tx = WorkbookTransaction(self, source, deadline)
        self._busy = True
        try:
            with tx:
                yield tx
        except Exception as error:
            if self.is_fatal(error):
                self.invalidate(error)
            context = tx.error_context()
            if isinstance(error, WorkbookControllerError):
                error.add_context(**context)
                raise
            wrapped = DeadSessionError if self.is_fatal(error) else WorkbookIOError
            raise wrapped(
                f"Workbook operation failed during {tx.phase}", **context
            ) from error
        finally:
            self._busy = False

    @contextmanager
    def bind_session(self, session: Session, /) -> Iterator[ControllerBase]:
        raise ConfigurationError(
            "Borrowed-session refresh is not supported: the save watchdog can terminate "
            "the caller's Excel process. Use an owned controller."
        )
        yield self
