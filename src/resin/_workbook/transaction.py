"""Owned workbook transactions and conservative filesystem publication."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from enum import StrEnum
from pathlib import Path
import shutil, tempfile, hashlib, os
from typing import (Any, TYPE_CHECKING, TypeVar, Generator, Generic)
from uuid import uuid4
import win32com.client as win32
from lute import get_logger, LogMsg

from .types import (
    PublicationDisposition, RefreshOutcome, RefreshStatus,
    
)
from .exceptions import (PublicationError, WorkbookControllerError, WorkbookIOError,)
from .deadline import Deadline

if TYPE_CHECKING:
    from .base_controller import BaseController

mlog = get_logger(__name__)
T = TypeVar("T")
PhaseT = TypeVar('PhaseT', bound=(str | StrEnum))

def fingerprint(path: Path, deadline: Deadline) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            deadline.check("file fingerprint")
            digest.update(block)
    return digest.hexdigest()


@contextmanager
def publication_lock(path: Path, deadline: Deadline) -> Generator[None]:
    lock = path.with_name(f".{path.name}.resin-publish.lock")
    while True:
        deadline.check("publication lock")
        try: fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError: deadline.pause()
        else: break
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(f"pid={os.getpid()}\n")
        yield
    finally:
        lock.unlink()


def publish(
    staged: Path, 
    dst: Path, 
    baseline: str, 
    deadline: Deadline
) -> Path:
    """Coordinate resin writers; detect external edits, but do not claim remote CAS."""
    sibling = dst.with_name(
        f".{dst.stem}.resin-{uuid4().hex}{dst.suffix}"
    )
    backup = dst.with_name(
        f"{dst.stem}.backup.{uuid4().hex}{dst.suffix}"
    )
    try:
        with publication_lock(dst, deadline):
            if fingerprint(dst, deadline) != baseline:
                raise PublicationError("Original workbook changed since staging")
            deadline.check("publication copy")
            shutil.copy2(staged, sibling)
            if fingerprint(sibling, deadline) != fingerprint(staged, deadline):
                raise PublicationError("Published copy failed content verification")
            shutil.copy2(dst, backup)
            if fingerprint(backup, deadline) != baseline:
                raise PublicationError("Original changed while creating backup")
            if fingerprint(dst, deadline) != baseline:
                raise PublicationError("Original changed before replacement")
            deadline.check("publication replacement")
            os.replace(sibling, dst)
    except Exception as e:
        context = dict(
            original_path=dst, recovery_path=staged,
            temporary_path=sibling, backup_path=backup,
        )
        if isinstance(e, WorkbookControllerError):
            e.add_context(**context)
            raise
        raise PublicationError("Workbook publication failed", **context) from e
    return backup


class WorkbookTransaction(Generic[PhaseT]):
    phase: str | PhaseT
    def __init__(self, owner: BaseController, path: Path, deadline: Deadline) -> None:
        self.owner = owner
        self.original_path = path
        self.staged_path = path
        self.deadline = deadline
        self.operation_id = uuid4().hex
        self.started_at = owner._now()
        self.started_monotonic = deadline.clock()
        self.phase = "staging"
        self.last_timestamp: datetime | None = None
        self._wb: win32.CDispatch | None = None
        self._directory: Path | None = None
        self._baseline: str | None = None
        self._committed = False
        self._retain = False
        self.publication = PublicationDisposition.NOT_ATTEMPTED

    @property
    def wb(self) -> win32.CDispatch:
        if self._wb is None:
            raise WorkbookIOError("Workbook handle is not open")
        return self._wb

    def error_context(self) -> dict[str, object]:
        return dict(
            phase=self.phase, 
            operation_id=self.operation_id,
            original_path=self.original_path, 
            staged_path=self.staged_path,
            recovery_path=self.staged_path if self._retain else None,
            pid=self.owner._pid,
            last_timestamp=self.last_timestamp,
        )

    def __enter__(self) -> WorkbookTransaction:
        try:
            self.deadline.check(self.phase)
            if self.owner.should_stage(self.original_path):
                self._directory = Path(tempfile.mkdtemp(
                    prefix=f"{self.operation_id}-", dir=self.owner.run_directory
                ))
                self.staged_path = self._directory / self.original_path.name
                self._baseline = fingerprint(self.original_path, self.deadline)
                shutil.copy2(self.original_path, self.staged_path)
                if fingerprint(self.staged_path, self.deadline) != self._baseline:
                    raise WorkbookIOError("Original changed during staging")
            self.phase = "open"
            self.deadline.check(self.phase)
            self._wb = self.owner.session.open_workbook(self.staged_path)
            self.owner._targets[id(self._wb)] = self._wb
            if bool(self._wb.ReadOnly):
                raise WorkbookIOError("Workbook opened read-only")
            self.deadline.check(self.phase)
            return self
        except BaseException:
            self._retain = True
            self._close_preserving_error()
            try:
                self._cleanup_files()
            except Exception:
                mlog.exception("Secondary failure retaining failed workbook staging")
            raise

    def _close(self) -> None:
        wb = self._wb
        if wb is None:
            return
        session = self.owner._session
        if session is None:
            raise WorkbookIOError("Lost Excel session before closing workbook")
        try:
            session.close_workbook(wb, save_changes=False)
        except Exception:
            # Retain registry entry so controller teardown can retry a failed close.
            self.owner.invalidate(WorkbookIOError("Target workbook close failed"))
            raise
        else:
            self.owner._targets.pop(id(wb), None)
            self._wb = None

    def _close_preserving_error(self) -> None:
        try:
            self._close()
        except Exception:
            mlog.exception("Secondary error closing failed workbook operation")

    def _cleanup_files(self) -> None:
        directory = self._directory
        if directory is None:
            return
        if self._retain:
            self.owner._retained.add(directory)
            mlog.warning("Workbook operation recovery directory: %s", directory)
            return
        if self.staged_path.exists():
            self.staged_path.unlink()
        directory.rmdir()

    def commit(self) -> PublicationDisposition:
        """
        - handles saving, closing, and publishing (optional)
        """
        if self._committed:
            raise WorkbookIOError("Workbook transaction already committed")
        self.phase = "save"
        self.owner.session.save_workbook(self.wb, timeout=self.deadline.remaining())
        self.deadline.check(self.phase)
        self.phase = "close"
        self._close()
        self.deadline.check(self.phase)
        if self._baseline is not None:
            self.phase = "publish"
            publish(self.staged_path, self.original_path, self._baseline, self.deadline)
            self.publication = PublicationDisposition.PUBLISHED
        else:
            self.publication = PublicationDisposition.IN_PLACE
        self._committed = True
        self.phase = "complete"
        return self.publication

    def outcome(
        self,
        status: RefreshStatus,
        previous: datetime | None,
        refreshed: datetime | None,
        details: T,
        *,
        skip_reason: str | None = None,
        cooldown_remaining_seconds: float = 0,
        message: str | LogMsg | None=None
    ) -> RefreshOutcome[T]:
        if status == RefreshStatus.REFRESHED and not self._committed:
            raise WorkbookIOError("A refreshed outcome requires a committed workbook")
        if status == RefreshStatus.SKIPPED_COOLDOWN:
            if self._committed:
                raise WorkbookIOError("A committed workbook cannot be reported as skipped")
            self.phase = "close"
            self._close()
            self.deadline.check(self.phase)
        return RefreshOutcome(
            status=status, 
            path=self.original_path, 
            operation_id=self.operation_id,
            started_at=self.started_at, 
            ended_at=self.owner._now(),
            elapsed_seconds=self.deadline.clock() - self.started_monotonic,
            previous_refreshed_at=previous, 
            refreshed_at=refreshed,
            publication=self.publication, 
            details=details, 
            skip_reason=skip_reason,
            cooldown_remaining_seconds=cooldown_remaining_seconds,
            message=message
        )

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if exc is not None:
            self._retain = True
            self._close_preserving_error()
        else:
            try:
                self._close()
            except BaseException:
                self._retain = True
                self._cleanup_files()
                raise
        try:
            self._cleanup_files()
        except Exception:
            if exc is None:
                raise
            mlog.exception("Secondary failure cleaning workbook staging")
        return False
