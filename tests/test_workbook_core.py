from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch

from resin._workbook import (
    ConfigurationError, ControllerBase, ControllerState, DeadSessionError,
    Deadline, PublicationDisposition, PublicationError, RefreshStatus,
    RefreshTimeoutError, WorkbookControllerError, WorkbookIOError,
    cooldown_remaining, parse_refresh_timestamp, read_workbook_name,
    validate_duration,
)
from resin._workbook.transaction import fingerprint, publish


class Clock:
    def __init__(self):
        self.value = 0.0
        self.pumps = 0

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds

    def pump(self):
        self.pumps += 1


class FakeSession:
    def __init__(self):
        self.pid = 123
        self.events = []
        self.excel = SimpleNamespace(Ready=True, CalculationState=0)
        self.fail_save = None
        self.fail_close = None
        self.readonly = False

    def __enter__(self):
        self.events.append("enter")
        return self

    def __exit__(self, *exc):
        self.events.append("exit")
        return False

    def open_workbook(self, path):
        wb = SimpleNamespace(path=Path(path), ReadOnly=self.readonly)
        self.events.append(("open", path))
        return wb

    def close_workbook(self, wb, save_changes=False):
        self.events.append(("close", wb.path, save_changes))
        if self.fail_close:
            raise self.fail_close

    def save_workbook(self, wb, timeout=20):
        self.events.append(("save", wb.path, timeout))
        if self.fail_save:
            raise self.fail_save
        wb.path.write_bytes(b"refreshed workbook")


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.guard = patch(
            "win32com.client.DispatchEx",
            side_effect=AssertionError("Live Excel automation forbidden in unit tests"),
        )
        self.guard.start()
        self.addCleanup(self.guard.stop)
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "example.xlsm"
        self.path.write_bytes(b"original workbook")
        self.clock = Clock()
        self.session = FakeSession()
        self.now = datetime(2026, 11, 4)

    def controller(self, **kwargs):
        return ControllerBase(
            staging=self.root / "staging", session_factory=lambda: self.session,
            clock=self.clock, sleep=self.clock.sleep, pump=self.clock.pump,
            now=lambda: self.now, **kwargs,
        )

    def deadline(self, seconds=10):
        return Deadline(
            seconds, clock=self.clock, sleep=self.clock.sleep, pump=self.clock.pump
        )

    def test_options_do_not_create_staging_and_instances_are_single_use(self):
        ctrl = self.controller()
        self.assertFalse(ctrl.staging.exists())
        with ctrl:
            self.assertEqual(ctrl.state, ControllerState.READY)
            with self.assertRaises(WorkbookControllerError):
                ctrl.__enter__()
        self.assertEqual(ctrl.state, ControllerState.CLOSED)
        with self.assertRaises(WorkbookControllerError):
            ctrl.__enter__()
        with self.assertRaises(DeadSessionError):
            with ctrl.operation(self.path):
                pass

    def test_use_before_entry_and_borrowed_session_rejected(self):
        ctrl = self.controller()
        with self.assertRaises(DeadSessionError):
            with ctrl.operation(self.path):
                pass
        with self.assertRaises(ConfigurationError):
            with ctrl.bind_session(self.session):
                pass
        self.assertEqual(self.session.events, [])

    def test_skip_closes_without_save_or_publish(self):
        with self.controller() as ctrl:
            with ctrl.operation(self.path) as tx:
                outcome = tx.outcome(
                    RefreshStatus.SKIPPED_COOLDOWN, self.now, self.now, None,
                    skip_reason="cooldown", cooldown_remaining_seconds=1,
                )
                staged = tx.staged_path
            self.assertFalse(staged.exists())
            self.assertEqual(outcome.publication, PublicationDisposition.NOT_ATTEMPTED)
        self.assertEqual(self.path.read_bytes(), b"original workbook")
        self.assertEqual([e[0] for e in self.session.events if isinstance(e, tuple)],
                         ["open", "close"])

    def test_commit_saves_closes_and_publishes_preserving_original_backup(self):
        with self.controller() as ctrl:
            with ctrl.operation(self.path) as tx:
                self.assertEqual(tx.commit(), PublicationDisposition.PUBLISHED)
                result = tx.outcome(RefreshStatus.REFRESHED, None, self.now, "details")
            run = ctrl.run_directory
        self.assertFalse(run.exists())
        self.assertEqual(self.path.read_bytes(), b"refreshed workbook")
        backups = list(self.root.glob("example.backup.*.xlsm"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), b"original workbook")
        self.assertEqual(result.details, "details")
        self.assertEqual(self.session.events[-1], "exit")

    def test_in_place_save_is_explicit(self):
        with self.controller(staging_policy="never") as ctrl:
            with ctrl.operation(self.path) as tx:
                self.assertEqual(tx.staged_path, self.path)
                self.assertEqual(tx.commit(), PublicationDisposition.IN_PLACE)
        self.assertEqual(self.path.read_bytes(), b"refreshed workbook")

    def test_error_retains_staging_without_overwriting_original(self):
        self.session.fail_save = OSError("disk full")
        with self.controller() as ctrl:
            with self.assertRaises(WorkbookIOError) as caught:
                with ctrl.operation(self.path) as tx:
                    staged = tx.staged_path
                    tx.commit()
            self.assertEqual(ctrl.state, ControllerState.READY)
            self.assertIs(caught.exception.__cause__, self.session.fail_save)
            self.assertEqual(caught.exception.context["recovery_path"], staged)
        self.assertTrue(staged.exists())
        self.assertEqual(self.path.read_bytes(), b"original workbook")

    def test_conflict_retains_refreshed_output_and_external_edit(self):
        with self.controller() as ctrl:
            with self.assertRaises(PublicationError):
                with ctrl.operation(self.path) as tx:
                    self.path.write_bytes(b"external edit")
                    staged = tx.staged_path
                    tx.commit()
        self.assertEqual(staged.read_bytes(), b"refreshed workbook")
        self.assertEqual(self.path.read_bytes(), b"external edit")

    def test_same_basename_sources_and_repeat_operations_have_unique_paths(self):
        other = self.root / "other" / self.path.name
        other.parent.mkdir()
        other.write_bytes(b"other")
        paths = []
        with self.controller() as ctrl:
            for path in (self.path, other, self.path):
                with ctrl.operation(path) as tx:
                    paths.append(tx.staged_path)
        self.assertEqual(len(set(paths)), 3)

    def test_reentrant_and_wrong_thread_use_rejected(self):
        with self.controller() as ctrl:
            errors = []
            def use_from_thread():
                try:
                    with ctrl.operation(self.path):
                        pass
                except WorkbookControllerError as error:
                    errors.append(error)
            thread = threading.Thread(target=use_from_thread)
            thread.start()
            thread.join()
            self.assertEqual(len(errors), 1)
            with ctrl.operation(self.path):
                with self.assertRaises(WorkbookControllerError):
                    with ctrl.operation(self.path):
                        pass

    def test_readonly_open_is_closed_and_never_saved(self):
        self.session.readonly = True
        with self.controller() as ctrl:
            with self.assertRaises(WorkbookIOError):
                with ctrl.operation(self.path):
                    pass
        self.assertEqual(len([e for e in self.session.events if e[0] == "close"]), 1)

    def test_save_watchdog_failure_invalidates_session(self):
        from noxl.types import ExcelSaveTimeoutError
        self.session.fail_save = ExcelSaveTimeoutError("timeout")
        ctrl = self.controller()
        with ctrl:
            with self.assertRaises(DeadSessionError):
                with ctrl.operation(self.path) as tx:
                    tx.commit()
            self.assertEqual(ctrl.state, ControllerState.FAILED)
            with self.assertRaises(DeadSessionError):
                with ctrl.operation(self.path):
                    pass
        self.assertEqual(ctrl.state, ControllerState.FAILED)

    def test_startup_error_is_preserved_and_session_unwinds(self):
        error = ValueError("initialization failed")
        ctrl = self.controller()
        with patch.object(ctrl, "_on_enter", side_effect=error):
            with self.assertRaises(ValueError) as caught:
                ctrl.__enter__()
        self.assertIs(caught.exception, error)
        self.assertEqual(ctrl.state, ControllerState.FAILED)
        self.assertEqual(self.session.events, ["enter", "exit"])
        self.assertFalse(ctrl.run_directory.exists())

    def test_addin_cleanup_precedes_session_exit(self):
        ctrl = self.controller()
        with patch.object(ctrl, "_on_exit", side_effect=lambda: self.session.events.append("addin")):
            with ctrl:
                pass
        self.assertEqual(self.session.events, ["enter", "addin", "exit"])

    def test_cleanup_error_does_not_replace_primary(self):
        ctrl = self.controller()
        error = ValueError("primary")
        with patch.object(ctrl, "_on_exit", side_effect=OSError("cleanup")):
            with self.assertRaises(ValueError) as caught:
                with ctrl:
                    raise error
        self.assertIs(caught.exception, error)
        self.assertEqual(self.session.events[-1], "exit")

    def test_successful_body_surfaces_cleanup_failure(self):
        ctrl = self.controller()
        with patch.object(ctrl, "_on_exit", side_effect=OSError("cleanup")):
            with self.assertRaises(OSError):
                with ctrl:
                    pass
        self.assertEqual(self.session.events[-1], "exit")
        self.assertEqual(ctrl.state, ControllerState.FAILED)

    def test_primary_startup_error_survives_addin_cleanup_failure(self):
        ctrl = self.controller()
        primary = ValueError("startup")
        with patch.object(ctrl, "_on_enter", side_effect=primary):
            with patch.object(ctrl, "_on_exit", side_effect=OSError("cleanup")):
                with self.assertRaises(ValueError) as caught:
                    ctrl.__enter__()
        self.assertIs(caught.exception, primary)
        self.assertEqual(self.session.events[-1], "exit")

    def test_publication_lock_wait_respects_deadline_without_removing_foreign_lock(self):
        lock = self.path.with_name(f".{self.path.name}.resin-publish.lock")
        lock.write_text("foreign owner", encoding="ascii")
        staged = self.root / "stage.xlsx"
        staged.write_bytes(b"new")
        with self.assertRaises(RefreshTimeoutError):
            publish(staged, self.path, fingerprint(self.path, self.deadline()),
                    self.deadline(.5))
        self.assertEqual(lock.read_text(encoding="ascii"), "foreign owner")
        self.assertEqual(self.path.read_bytes(), b"original workbook")

    def test_failed_close_retains_file_until_controller_cleanup_retries(self):
        ctrl = self.controller()
        with ctrl:
            with self.assertRaises(WorkbookIOError):
                with ctrl.operation(self.path) as tx:
                    staged = tx.staged_path
                    self.session.fail_close = OSError("close failed")
            self.assertEqual(ctrl.state, ControllerState.FAILED)
            self.assertTrue(staged.exists())
            self.assertEqual(len(ctrl._targets), 1)
            self.session.fail_close = None
        self.assertEqual(ctrl._targets, {})

    def test_failed_replace_leaves_original_and_recovery_files(self):
        staged = self.root / "stage.xlsm"
        staged.write_bytes(b"new")
        baseline = fingerprint(self.path, self.deadline())
        with patch("resin._workbook.transaction.os.replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PublicationError) as caught:
                publish(staged, self.path, baseline, self.deadline())
        self.assertEqual(self.path.read_bytes(), b"original workbook")
        self.assertEqual(staged.read_bytes(), b"new")
        self.assertTrue(caught.exception.context["temporary_path"].is_file())
        self.assertTrue(caught.exception.context["backup_path"].is_file())
        self.assertFalse(list(self.root.glob("*.lock")))

    def test_deadline_is_monotonic_and_all_waits_share_budget(self):
        deadline = self.deadline(1)
        self.assertEqual(deadline.remaining(), 1)
        deadline.pause(.6)
        self.assertAlmostEqual(deadline.remaining(), .4)
        with self.assertRaises(RefreshTimeoutError):
            deadline.pause(.6)
        self.assertEqual(self.clock.value, 1)
        self.assertEqual(self.clock.pumps, 2)

    def test_no_refreshed_outcome_before_commit(self):
        with self.controller() as ctrl:
            with ctrl.operation(self.path) as tx:
                with self.assertRaises(WorkbookIOError):
                    tx.outcome(RefreshStatus.REFRESHED, None, self.now, None)

    def test_idle_wait_pumps_until_ready_or_timeout(self):
        self.session.excel.Ready = False
        with self.controller() as ctrl:
            with self.assertRaises(RefreshTimeoutError):
                ctrl.wait_for_idle(self.deadline(.5))
        self.assertGreater(self.clock.pumps, 0)

    def test_auto_staging_uses_roots_not_company_substrings(self):
        with self.controller(staging_policy="auto", stage_roots=(self.root,)) as ctrl:
            with ctrl.operation(self.path) as tx:
                self.assertNotEqual(tx.staged_path, self.path)


class TimestampTests(unittest.TestCase):
    def test_numeric_literals_datetime_and_date_systems(self):
        expected = datetime(2024, 1, 1, 12)
        for value in (45292.5, '=45292.5', '="45292.5"', expected):
            with self.subTest(value=value):
                self.assertEqual(parse_refresh_timestamp(value), expected)
        self.assertEqual(parse_refresh_timestamp(1, date1904=True), datetime(1904, 1, 2))
        self.assertEqual(parse_refresh_timestamp(1), datetime(1900, 1, 1))
        self.assertEqual(parse_refresh_timestamp(60), datetime(1900, 2, 28))
        self.assertIsNone(parse_refresh_timestamp(None))
        self.assertIsNone(parse_refresh_timestamp(""))
        self.assertIsNone(parse_refresh_timestamp(0))

    def test_malformed_and_error_variants_are_rejected(self):
        for value in (True, -2146826246, "=SUM(1,2)", "2024/01/01", float("nan"),
                      "x45292", float("inf"), object()):
            with self.subTest(value=value):
                with self.assertRaises(ConfigurationError):
                    parse_refresh_timestamp(value)

    def test_duration_validation_does_not_truncate_or_accept_bool(self):
        self.assertEqual(validate_duration(1.5, "test"), 1.5)
        for value in (True, "1", -1, 0, float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(ConfigurationError):
                    validate_duration(value, "test")

    def test_cooldown_boundaries_and_force(self):
        now = datetime(2026, 11, 4)
        self.assertEqual(cooldown_remaining(None, now, 30), 0)
        self.assertEqual(cooldown_remaining(now - timedelta(minutes=30), now, 30), 0)
        self.assertEqual(cooldown_remaining(now - timedelta(minutes=1), now, 30), 1740)
        self.assertEqual(cooldown_remaining(now + timedelta(minutes=1), now, 30), 1800)
        self.assertEqual(cooldown_remaining(now, now, 30, force=True), 0)

    def test_workbook_name_constant_and_range_values(self):
        entries = {
            "Text": SimpleNamespace(Name="Text", RefersTo='="quote ""ok"""'),
            "Number": SimpleNamespace(Name="Number", RefersTo="=45292.5"),
            "Cell": SimpleNamespace(Name="Cell", RefersTo="=Sheet1!$A$1",
                                    RefersToRange=SimpleNamespace(Value=42)),
        }
        class Names:
            def __iter__(self):
                return iter(entries.values())
            def __call__(self, name):
                return entries[name]
        wb = SimpleNamespace(Names=Names())
        self.assertEqual(read_workbook_name(wb, "Text"), 'quote "ok"')
        self.assertEqual(read_workbook_name(wb, "Number"), 45292.5)
        self.assertEqual(read_workbook_name(wb, "Cell"), 42)
        self.assertIsNone(read_workbook_name(wb, "Missing", missing_ok=True))


if __name__ == "__main__":
    unittest.main()
