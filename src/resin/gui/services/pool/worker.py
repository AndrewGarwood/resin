"""
*`@file`* `gui/services/pool/worker`
"""

from __future__ import annotations
from concurrent.futures import Future
from queue import Queue
import threading
from typing import Any
from pyqi import require
from resin.utils import runtime
from resin.gui.core.session import Session
from resin.gui.services.transaction import Transaction

from .command import SessionCommand, SessionCommandType
from .session_binding import SessionBinding


class SessionWorker:
    """
    Persistent worker for exactly one SAP GUI session.

    The worker:
    - owns one thread;
    - keeps COM initialized for the thread's lifetime;
    - resolves one Session wrapper;
    - executes submitted commands serially;
    - optionally closes its session during shutdown.
    """

    def __init__(
        self,
        worker_id: str,
        binding: SessionBinding,
        /,
    ) -> None:
        self.id = require.non_empty_string(
            worker_id,
            "Session worker ID",
        )
        self._binding = binding

        self._commands: Queue[SessionCommand] = Queue()
        self._ready = threading.Event()
        self._stopped = threading.Event()

        self._startup_error: BaseException | None = None
        self._fatal_error: BaseException | None = None

        self._session: Session | None = None
        self._current_transaction: Transaction | None = None

        self._thread = threading.Thread(
            target=self._run,
            name=f"sap-session-worker-{self.id}",
            daemon=False,
        )

    @property
    def binding(self) -> SessionBinding:
        return self._binding

    @property
    def is_alive(self) -> bool:
        return self._thread.is_alive()

    @property
    def is_ready(self) -> bool:
        return (
            self._ready.is_set()
            and self._startup_error is None
            and not self._stopped.is_set()
        )

    @property
    def session(self) -> Session | None:
        return self._session

    @property
    def current_transaction(self) -> Transaction | None:
        return self._current_transaction

    def start(
        self,
        *,
        timeout: float = 30.0,
    ) -> None:
        if self._ready.is_set():
            raise RuntimeError(
                f"Session worker {self.id!r} has already been started"
            )

        if self._thread.is_alive():
            raise RuntimeError(
                f"Session worker {self.id!r} is already running"
            )

        self._thread.start()

        if not self._ready.wait(timeout):
            raise TimeoutError(
                f"Session worker {self.id!r} did not initialize "
                f"within {timeout} seconds"
            )

        if self._startup_error is not None:
            raise RuntimeError(
                f"Session worker {self.id!r} failed to initialize"
            ) from self._startup_error

        if not self._thread.is_alive():
            raise RuntimeError(
                f"Session worker {self.id!r} stopped during startup"
            ) from self._fatal_error

    def submit(
        self,
        command_type: SessionCommandType,
        transaction: Transaction,
        /,
    ) -> Future[Any]:
        if not self.is_ready:
            raise RuntimeError(
                f"Session worker {self.id!r} is not available"
            )

        command = SessionCommand(
            type=command_type,
            transaction=transaction,
        )
        self._commands.put(command)
        return command.future

    def stop(self) -> Future[None]:
        future: Future[None] = Future()

        if not self._thread.is_alive():
            future.set_result(None)
            return future

        self._commands.put(
            SessionCommand(
                type=SessionCommandType.STOP,
                future=future,
            )
        )
        return future

    def join(
        self,
        timeout: float | None = None,
    ) -> None:
        """ *`@note`* waits for `self._thread` to terminate """
        self._thread.join(timeout)

        if self._thread.is_alive():
            raise TimeoutError(
                f"Session worker {self.id!r} did not stop"
            )

    def _run(self) -> None:
        """
        *`@note`* this method is the target of `self._thread`
        """
        try:
            with runtime.com_apartment():
                self._run_in_com_apartment()
        except BaseException as e:
            if not self._ready.is_set():
                self._startup_error = e
                self._ready.set()
            else:
                self._fatal_error = e
        finally:
            self._session = None
            self._current_transaction = None
            self._stopped.set()
            self._ready.set()

    def _run_in_com_apartment(self) -> None:
        """
        handles cleanup
        """
        try:
            session = self._binding.resolve()
            # Validate that the referenced SAP session exists.
            # Do not retain the returned dispatch object.
            session.gateway.get_session(
                session.connection_id,
                session.id,
            )
            self._session = session
        except BaseException as e:
            self._startup_error = e
            self._ready.set()
            return
        self._ready.set()
        try:
            self._command_loop()
        finally:
            self._close_owned_session()

    def _command_loop(self) -> None:
        while True:
            command = self._commands.get()

            try:
                if command.type is SessionCommandType.STOP:
                    command.future.set_result(None)
                    return
                transaction = command.transaction
                if transaction is None:
                    raise RuntimeError(
                        f"{command.type!r} requires a transaction"
                    )
                self._current_transaction = transaction
                result = self._execute_command(
                    command.type,
                    transaction,
                )
                if not command.future.done():
                    command.future.set_result(result)
            except BaseException as error:
                if not command.future.done():
                    command.future.set_exception(error)
            finally:
                self._commands.task_done()
                transaction = command.transaction
                if (transaction is not None
                    and transaction.is_terminal
                ):
                    self._current_transaction = None

                runtime.try_pump_waiting_messages()

    def _close_owned_session(self) -> None:
        session = self._session

        if session is None or not self._binding.close_on_exit:
            return
        try:
            session.close()
        except BaseException as error:
            # There is no command Future to receive a shutdown cleanup
            # failure, so preserve it as worker-level state.
            self._fatal_error = error

    def _execute_command(
        self,
        command_type: SessionCommandType,
        transaction: Transaction,
        /,
    ) -> Any:
        session = self._session
        if session is None:
            raise RuntimeError(
                f"Session worker {self.id!r} has no session"
            )
        match command_type:
            case SessionCommandType.PREPARE:
                transaction.open(session)
                transaction.populate_selection_screen(session)
                return None
            case SessionCommandType.EXECUTE:
                return transaction.execute(session)
            case SessionCommandType.POST_EXECUTE:
                return transaction.handle_post_execute(session)
            case SessionCommandType.EXPORT:
                return transaction.export(session)
            case _:
                raise RuntimeError(
                    f"Unsupported session command: {command_type!r}"
                )

__all__ = ["SessionWorker"]