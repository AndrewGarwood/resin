"""
*`@file`* `_workbook/base`
"""
from __future__ import annotations
import tempfile, sys
from datetime import datetime
from typing import (Any, Callable, Generator, TYPE_CHECKING)
import time, threading
from pywintypes import com_error
from contextlib import (contextmanager, ExitStack)
from pathlib import Path
from pyqi import (require)
from lute import LogMsg, get_logger
from .types import (StagingPolicy, ControllerState)
from .base_controller_options import (BaseControllerOptions, BaseControllerOptionsDict)
from .exceptions import (
    ConfigurationError, DeadSessionError, 
    WorkbookControllerError, WorkbookIOError
)
from resin.utils import runtime
from ._session_model import (SessionFactory, Session, default_session_factory)
from .deadline import (Deadline)

if TYPE_CHECKING:
    from .transaction import WorkbookTransaction


mlog = get_logger(__file__)

_SESSION_ACCESSIBLE_STATES = frozenset([
    ControllerState.ENTERING, 
    ControllerState.READY, 
    ControllerState.CLOSING,
])
_FATAL_HRESULTS = frozenset([
    -2147417848, 
    -2147023174, 
    -2147220995, 
    -2147023170
])

class BaseController():
    def __init__(
        self,
        options: BaseControllerOptions | BaseControllerOptionsDict,
        session_factory: SessionFactory | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        pump: Callable[[], None] = runtime.pump_waiting_messages,
        now: Callable[[], datetime] = datetime.now
    ):
        """
        - *`@param`* `session_factory` `() -> Session | None`
            - will default to `(function) default_session_factory() -> ExcelSession`
            - used as `context manager` arg in `stack.enter_context`
        """
        self.options = (
            BaseControllerOptions.from_dict(options) 
            if isinstance(options, dict) 
            else options
        )
        self._session_factory = session_factory or default_session_factory
        self._session: Session | None = None
        self._state = ControllerState.NEW
        self._clock, self._sleep, self._pump, self._now = clock, sleep, pump, now
        self._owner_thread: int | None = None
        self._stack: ExitStack | None = None

        self._run_directory: Path | None = None
        self._busy = False
        self._targets: dict[int, Any] = {}
        self._retained: set[Path] = set()

    @property
    def state(self): 
        return self._state
    
    @property
    def run_directory(self) -> Path:
        if self._run_directory is None:
            raise WorkbookControllerError("Controller has not been entered")
        return self._run_directory

    def _check_thread(self) -> None:
        if (self._owner_thread is not None 
            and self._owner_thread != threading.get_ident()
        ):
            raise WorkbookControllerError("Controller used from a different thread")

    @property
    def session(self) -> Session:
        self._check_thread()
        if self._session is None or self._state not in _SESSION_ACCESSIBLE_STATES:
            raise DeadSessionError("Controller has no usable Excel session")
        return self._session


    def deadline(self, timeout_seconds: float, /, poll_seconds: float | None=None):
        return Deadline(
            seconds=timeout_seconds, 
            clock=self._clock, 
            sleep=self._sleep, 
            pump=self._pump,
            poll_seconds=require.positive_number(
                poll_seconds or self.options.poll_seconds, 
                f"{self.__class__.__name__}.deadline(..., <poll_seconds>)"
                )
        )

    def __enter__(self):
        self._check_thread()
        if self._state != ControllerState.NEW:
            raise WorkbookControllerError("Controller objects are single-use")
        self._owner_thread = threading.get_ident()
        self._state = ControllerState.ENTERING

        stack = ExitStack()
        self._stack = stack
        try:
            deadline = self.deadline(self.options.startup_timeout_seconds)
            self.options.staging.mkdir(parents=True, exist_ok=True)
            self._run_directory = Path(tempfile.mkdtemp(
                prefix="resin-", 
                dir=self.options.staging
            ))
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
                mlog.exception(
                    "Encountered secondary failure after primary startup error"
                )
            finally:
                self._session = None
                self._stack = None
                self._state = ControllerState.FAILED
            raise
        return self
    
    def _on_enter(self, deadline: Deadline) -> None: # implement in child class
        pass

    def _on_exit(self) -> None: # implement in child class
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
            mlog.warning("Workbook recovery files retained at %s", root)

    def _close_targets(self) -> None:
        errors: list[Exception] = []
        for key, wb in list(self._targets.items())[::-1]:
            try:
                if self._session is not None:
                    self._session.close_workbook(wb, save_changes=False)
            except Exception as error:
                mlog.exception("Failed closing controller-owned workbook")
                errors.append(error)
            finally:
                self._targets.pop(key, None)
        if errors:
            raise WorkbookIOError("Failed closing controller-owned workbooks") from errors[0]

    def invalidate(self, error: BaseException, /) -> None:
        self._state = ControllerState.FAILED
        mlog.error("Excel session invalidated (%s)", type(error).__name__)
    
    @staticmethod
    def is_fatal(error: BaseException) -> bool:
        from noxl.types import ExcelSaveTimeoutError
        seen: set[int] = set()
        current: BaseException | None = error
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if isinstance(current, (ExcelSaveTimeoutError, DeadSessionError)):
                return True
            if getattr(current, "hresult", None) in _FATAL_HRESULTS:
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
                if (getattr(error, "hresult", None) not in {
                    -2147418111, 
                    -2147417846
                }):
                    raise
            deadline.pause()

    def should_stage(self, path: Path) -> bool:
        if self.options.staging_policy == StagingPolicy.ALWAYS:
            return True
        if self.options.staging_policy == StagingPolicy.NEVER:
            return False
        return (
            str(path).startswith("\\\\") 
            or any(
                path.is_relative_to(root) 
                for root in self.options.stage_roots
            )
        )

    @contextmanager
    def operation(
        self, 
        path: Path, 
        timeout_minutes: float = 30
    ) -> Generator[WorkbookTransaction]:
        from .transaction import WorkbookTransaction

        self._check_thread()
        if self._state != ControllerState.READY:
            raise DeadSessionError("Refresh requires a READY controller")
        if self._busy:
            raise WorkbookControllerError("Concurrent/reentrant workbook operation rejected")
        deadline = self.deadline(
            require.positive_number(timeout_minutes, "timeout_minutes") * 60
        )
        source = path
        txn = WorkbookTransaction(self, source, deadline)
        self._busy = True
        try:
            with txn: yield txn
        except Exception as e:
            if self.is_fatal(e):
                self.invalidate(e)
            context = txn.error_context()
            if isinstance(e, WorkbookControllerError):
                e.add_context(**context)
                raise
            wrapped = DeadSessionError if self.is_fatal(e) else WorkbookIOError
            raise wrapped(
                f"Workbook operation failed during {txn.phase}", **context
            ) from e
        finally:
            self._busy = False

    # @contextmanager
    # def bind_session(self, session: Session, /) -> Generator[BaseController]:
    #     raise ConfigurationError(
    #         "Borrowed-session refresh is not supported: the save watchdog can terminate "
    #         "the caller's Excel process. Use an owned controller."
    #     )
    #     yield self



__all__ = ["BaseController"]