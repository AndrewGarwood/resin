"""AO contract tests: fake COM only; no ExcelSession is ever constructed."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from resin._workbook import (
    ConfigurationError, ConnectionBindingError, ControllerState,
    DeadSessionError, PublicationDisposition, RefreshStatus, RefreshTimeoutError,
)
from resin.ao import (
    AoCmd, AoCommandError, AoMacro, AoProp, Controller, ControllerOptions,
    DefaultValueOptions, ExcelComValueError, WorkbookOptions, WorkbookProperty,
    ensure_sap_ao_ready, require_ao_bool,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.pumps = 0

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds

    def pump(self) -> None:
        self.pumps += 1


class FakeComError(Exception):
    def __init__(self, hresult: int, message: str = "COM failure") -> None:
        super().__init__(hresult, message)
        self.hresult = hresult


class FakeWorkbook:
    Date1904 = False
    ReadOnly = False

    def __init__(self, path: Path, events: list[tuple]) -> None:
        self.FullName = str(path)
        self.Name = path.name
        self.events = events

    def Activate(self) -> None:
        self.events.append(("activate",))


class FakeExcel:
    CalculationState = 0
    Ready = True

    def __init__(self, clock: FakeClock, events: list[tuple]) -> None:
        self.clock = clock
        self.events = events
        self.timestamp: object = datetime(2026, 11, 1, 8)
        self.last_error: object = (0, "")
        self.active: object = 1
        self.connected: object = 1
        self.refresh_count = 0
        self.advance_initial = True
        self.advance_final = True
        self.failures: dict[tuple, deque] = {}
        self.prompt_calls: list[tuple] = []
        self.delayed_reads = 0
        self.pending_timestamp: datetime | None = None
        self.advance_clock_on_prompt = 0.0

    def fail(self, key: tuple, *results: object) -> None:
        self.failures[key] = deque(results)

    def Run(self, macro: str, *args: object) -> object:
        event = (macro, *args)
        self.events.append(event)
        key = event if event in self.failures else (macro,)
        failures = self.failures.get(key)
        if failures:
            result = failures.popleft()
            if isinstance(result, BaseException):
                raise result
            return result
        if macro == AoMacro.GET_PROPERTY:
            return {
                AoProp.LAST_ERROR: self.last_error,
                AoProp.IS_DATA_SOURCE_ACTIVE: self.active,
                AoProp.IS_CONNECTED: self.connected,
                AoProp.IS_AUTO_REFRESH: 1,
                AoProp.CHANGED_CROSSTABS: ("Crosstab1",),
                AoProp.CHANGED_DATASOURCES: ("DS_1",),
            }.get(args[0], 0)
        if macro == AoMacro.GET_WORKBOOK_INFO:
            if args[0] != WorkbookProperty.LAST_REFRESHED_AT:
                return "fake workbook"
            if self.pending_timestamp is not None:
                if self.delayed_reads:
                    self.delayed_reads -= 1
                else:
                    self.timestamp = self.pending_timestamp
                    self.pending_timestamp = None
            return self.timestamp
        if macro == AoMacro.EXEC_CMD and args[0] == AoCmd.REFRESH_DATA:
            self.refresh_count += 1
            advance = self.advance_initial if self.refresh_count == 1 else self.advance_final
            if advance:
                baseline = self.timestamp if isinstance(self.timestamp, datetime) else datetime(2026, 11, 1, 8)
                self.pending_timestamp = baseline + timedelta(seconds=1)
            return 1
        if macro == AoMacro.SET_VAR:
            self.prompt_calls.append(args)
            self.clock.value += self.advance_clock_on_prompt
            self.last_error = (0, "")
            return 1
        return 1


class FakeSession:
    pid = 12345

    def __init__(self, clock: FakeClock) -> None:
        self.events: list[tuple] = []
        self.excel = FakeExcel(clock, self.events)
        self.addin = SimpleNamespace(Connect=False)
        self.closed: list[FakeWorkbook] = []
        self.saved: list[FakeWorkbook] = []
        self.opened: list[FakeWorkbook] = []
        self.addins_requested: list[str] = []

    def __enter__(self) -> FakeSession:
        self.events.append(("enter",))
        return self

    def __exit__(self, *args: object) -> None:
        self.events.append(("exit",))

    def get_com_addin(self, name: str) -> object:
        self.addins_requested.append(name)
        return self.addin

    def open_workbook(self, path: Path) -> FakeWorkbook:
        wb = FakeWorkbook(path, self.events)
        self.opened.append(wb)
        self.events.append(("open", str(path)))
        return wb

    def add_workbook(self, path: Path) -> FakeWorkbook:
        return self.open_workbook(path)

    def save_workbook(self, wb: FakeWorkbook, timeout: float) -> None:
        if timeout <= 0:
            raise AssertionError("Save called after timeout")
        self.saved.append(wb)
        self.events.append(("save",))
        Path(wb.FullName).write_bytes(b"fake COM saved workbook")

    def close_workbook(self, wb: FakeWorkbook, save_changes: bool = False) -> None:
        if save_changes:
            raise AssertionError("Unexpected implicit save")
        self.closed.append(wb)
        self.events.append(("close",))


class AoControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parent / f".ao-test-{uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root)
        self.path = self.root / "report.xlsm"
        self.path.write_bytes(b"fake workbook fixture, not an Excel document")
        self.clock = FakeClock()
        self.session = FakeSession(self.clock)
        self.options = ControllerOptions(self.root / "staging", refresh_cooldown_minutes=0)
        self.fo = WorkbookOptions(self.path, prompts={"P": "secret-value"}, ds_alias="REPORT_DS")
        # A regression must fail rather than opening a real Excel application.
        self.live_factory = patch(
            "resin._workbook.lifecycle.default_session_factory",
            side_effect=AssertionError("Live Excel forbidden"),
        )
        self.live_factory.start()
        self.addCleanup(self.live_factory.stop)

    def controller(self, **kwargs: object) -> Controller:
        return Controller(
            self.options, session_factory=lambda: self.session, clock=self.clock,
            sleep=self.clock.sleep, pump=self.clock.pump, poll_seconds=.1,
            now=lambda: datetime(2026, 11, 4), **kwargs,
        )

    def commands(self) -> list[tuple]:
        return [
            event for event in self.session.events
            if event[0] in (AoMacro.EXEC_CMD, AoMacro.SET_REFRESH, AoMacro.SET_VAR)
        ]

    def test_refresh_order_and_publication(self) -> None:
        with self.controller() as controller:
            result = controller.refresh(self.fo, True)
        self.assertEqual(self.commands(), [
            (AoMacro.EXEC_CMD, AoCmd.REFRESH_DATA),
            (AoMacro.SET_REFRESH, "Off"),
            (AoMacro.EXEC_CMD, AoCmd.PAUSE_VARIABLE_SUBMIT, "On"),
            (AoMacro.SET_VAR, "P", "secret-value", "", "REPORT_DS"),
            (AoMacro.SET_REFRESH, "On"),
            (AoMacro.EXEC_CMD, AoCmd.PAUSE_VARIABLE_SUBMIT, "Off"),
            (AoMacro.EXEC_CMD, AoCmd.REFRESH_DATA),
        ])
        self.assertEqual(result.status, RefreshStatus.REFRESHED)
        self.assertEqual(result.publication, PublicationDisposition.PUBLISHED)
        self.assertEqual(result.refreshed_at, datetime(2026, 11, 1, 8, 0, 2))
        self.assertEqual(result.details.prompts_applied, ("P",))
        self.assertTrue(result.details.completion_verified)
        self.assertFalse(result.details.live_semantics_verified)
        self.assertNotIn("secret-value", repr(result))
        self.assertEqual(len(result.details.command_responses), 7)
        self.assertEqual(self.path.read_bytes(), b"fake COM saved workbook")
        self.assertEqual(len(self.session.closed), 1)
        self.assertEqual(len(self.session.saved), 1)
        self.assertGreater(self.clock.pumps, 0)

    def test_legacy_positional_prompt_flag_and_none_return(self) -> None:
        with self.controller() as controller:
            self.assertIsNone(controller.refresh_workbook(self.fo, True, 1, True))
        self.assertEqual(len(self.session.excel.prompt_calls), 1)

    def test_new_api_respects_option_prompt_flag_legacy_default_does_not(self) -> None:
        self.fo.set_prompts = True
        with self.controller() as controller:
            controller.refresh(self.fo)
            controller.refresh_workbook(self.fo)
        self.assertEqual(len(self.session.excel.prompt_calls), 1)

    def test_cooldown_closes_without_resolving_or_writing(self) -> None:
        self.options.refresh_cooldown_minutes = 30
        self.session.excel.timestamp = datetime(2026, 11, 4)
        with patch("resin.ao.controller._field.resolve_field_dict") as resolve:
            with self.controller() as controller:
                result = controller.refresh(self.fo, True)
            resolve.assert_not_called()
        self.assertEqual(result.status, RefreshStatus.SKIPPED_COOLDOWN)
        self.assertEqual(result.cooldown_remaining_seconds, 1800)
        self.assertEqual(result.publication, PublicationDisposition.NOT_ATTEMPTED)
        self.assertEqual(result.details.prompts_applied, ())
        self.assertEqual(len(self.session.closed), 1)
        self.assertEqual(self.session.saved, [])
        self.assertEqual(self.commands(), [])

    def test_force_bypasses_cooldown(self) -> None:
        self.options.refresh_cooldown_minutes = 30
        self.session.excel.timestamp = datetime(2026, 11, 4)
        with self.controller() as controller:
            result = controller.refresh(self.fo, force=True)
        self.assertEqual(result.status, RefreshStatus.REFRESHED)

    def test_resolves_all_prompts_once_before_writes_and_retry(self) -> None:
        self.fo.prompts = {"P": {"sentinel": "CURRENT_DAY"}, "Q": "CURRENT_DAY"}
        self.session.excel.fail((AoMacro.SET_VAR,), 0)
        self.session.excel.last_error = (31, "datasource unavailable")
        # The initial readiness path must be clear; make LastError transient only
        # on the failed SAPSetVariable attempt.
        original_run = self.session.excel.Run

        def run(macro: str, *args: object) -> object:
            result = original_run(macro, *args)
            if macro == AoMacro.SET_VAR and result == 0:
                self.session.excel.last_error = (31, "datasource unavailable")
            return result

        self.session.excel.last_error = (0, "")
        with patch.object(self.session.excel, "Run", side_effect=run):
            with patch("resin.ao.controller._field.resolve_field_dict", return_value={"P": "once", "Q": "twice"}) as resolve:
                with self.controller() as controller:
                    controller.refresh(self.fo, True)
                resolve.assert_called_once_with(self.fo.prompts)
        attempts = [event for event in self.commands() if event[0] == AoMacro.SET_VAR]
        self.assertEqual(attempts[0][2], "once")
        self.assertEqual(attempts[1][2], "once")
        self.assertEqual(attempts[2][2], "twice")
        self.assertGreaterEqual(self.clock.value, .1)

    def test_resolver_escape_hatch_and_no_prompts(self) -> None:
        with patch("resin.ao.controller._field.resolve_field_dict") as resolve:
            with self.controller() as controller:
                controller.refresh(self.fo, True, resolve_prompts=False)
            resolve.assert_not_called()
        self.assertEqual(self.session.excel.prompt_calls[0][1], "secret-value")

    def test_real_field_resolver_and_configuration_unchanged(self) -> None:
        definition = {"sentinel": "FIRST_DAY_OF_YEAR", "year": 2024}
        self.fo.prompts = {"P": definition}
        with self.controller() as controller:
            controller.refresh(self.fo, True)
        self.assertEqual(self.session.excel.prompt_calls[0][1], "01/01/2024")
        self.assertEqual(definition, {"sentinel": "FIRST_DAY_OF_YEAR", "year": 2024})

    def test_prompt_rejection_restores_and_does_not_poison_usable_session(self) -> None:
        self.session.excel.fail((AoMacro.SET_VAR,), 0)
        with self.controller() as controller:
            with self.assertRaises(AoCommandError) as caught:
                controller.refresh(self.fo, True)
            self.assertEqual(controller.state, ControllerState.READY)
            self.assertNotIn("secret-value", str(caught.exception))
            self.assertEqual(self.commands()[-2:], [
                (AoMacro.SET_REFRESH, "On"),
                (AoMacro.EXEC_CMD, AoCmd.PAUSE_VARIABLE_SUBMIT, "Off"),
            ])
        self.assertEqual(self.session.saved, [])
        self.assertEqual(len(self.session.closed), 1)
        self.assertEqual(self.path.read_bytes(), b"fake workbook fixture, not an Excel document")

    def test_failed_restoration_poisoned_preserves_original_prompt_error(self) -> None:
        self.session.excel.fail((AoMacro.SET_VAR,), 0)
        self.session.excel.fail((AoMacro.SET_REFRESH, "On"), 0)
        with self.controller() as controller:
            with self.assertRaisesRegex(AoCommandError, "prompt"):
                controller.refresh(self.fo, True)
            self.assertEqual(controller.state, ControllerState.FAILED)
            with self.assertRaises(DeadSessionError):
                controller.refresh(self.fo)
        self.assertEqual(self.commands()[-1], (AoMacro.EXEC_CMD, AoCmd.PAUSE_VARIABLE_SUBMIT, "Off"))

    def test_pause_failure_also_attempts_restoration(self) -> None:
        self.session.excel.fail((AoMacro.EXEC_CMD, AoCmd.PAUSE_VARIABLE_SUBMIT, "On"), 0)
        with self.controller() as controller:
            with self.assertRaises(AoCommandError):
                controller.refresh(self.fo, True)
            self.assertEqual(controller.state, ControllerState.READY)
        self.assertEqual(self.commands()[-2:], [
            (AoMacro.SET_REFRESH, "On"),
            (AoMacro.EXEC_CMD, AoCmd.PAUSE_VARIABLE_SUBMIT, "Off"),
        ])

    def test_final_timestamp_must_advance_not_just_initial_refresh(self) -> None:
        self.session.excel.advance_final = False
        with self.controller() as controller:
            with self.assertRaises(RefreshTimeoutError):
                controller.refresh(self.fo, timeout_minutes=.01)
            self.assertEqual(controller.state, ControllerState.READY)
        self.assertEqual(self.session.saved, [])
        self.assertEqual(len(self.session.closed), 1)

    def test_initial_timestamp_must_advance_before_prompts(self) -> None:
        self.session.excel.advance_initial = False
        with self.controller() as controller:
            with self.assertRaises(RefreshTimeoutError):
                controller.refresh(self.fo, True, timeout_minutes=.01)
        self.assertEqual(self.session.excel.prompt_calls, [])
        self.assertEqual(len(self.commands()), 1)

    def test_delayed_timestamp_is_polled_before_save(self) -> None:
        self.session.excel.delayed_reads = 2
        with self.controller() as controller:
            result = controller.refresh(self.fo)
        self.assertTrue(result.details.completion_verified)
        self.assertGreaterEqual(self.clock.value, .2)

    def test_initial_command_rejection_stops_before_prompts(self) -> None:
        self.session.excel.fail((AoMacro.EXEC_CMD, AoCmd.REFRESH_DATA), 0)
        with self.controller() as controller:
            with self.assertRaises(AoCommandError):
                controller.refresh(self.fo, True)
            self.assertEqual(controller.state, ControllerState.READY)
        self.assertEqual(self.session.saved, [])
        self.assertEqual(len(self.commands()), 1)

    def test_advanced_timestamp_without_excel_readiness_cannot_save(self) -> None:
        original_run = self.session.excel.Run

        def run(macro: str, *args: object) -> object:
            result = original_run(macro, *args)
            if self.session.excel.refresh_count == 2:
                self.session.excel.Ready = False
            return result

        with patch.object(self.session.excel, "Run", side_effect=run):
            with self.controller() as controller:
                with self.assertRaises(RefreshTimeoutError):
                    controller.refresh(self.fo, timeout_minutes=.01)
        self.assertEqual(self.session.saved, [])

    def test_final_ao_error_cannot_save_even_after_successful_command(self) -> None:
        original_run = self.session.excel.Run

        def run(macro: str, *args: object) -> object:
            result = original_run(macro, *args)
            if self.session.excel.refresh_count == 2:
                self.session.excel.last_error = (99, "secret-value")
            return result

        with patch.object(self.session.excel, "Run", side_effect=run):
            with self.controller() as controller:
                with self.assertRaises(AoCommandError) as caught:
                    controller.refresh(self.fo)
        self.assertNotIn("secret-value", str(caught.exception))
        self.assertEqual(self.session.saved, [])

    def test_datasource_must_be_connected_as_well_as_active(self) -> None:
        self.session.excel.connected = 0
        with self.controller() as controller:
            with self.assertRaises(RefreshTimeoutError):
                controller.refresh(self.fo, timeout_minutes=.01)
        self.assertEqual(self.commands(), [])
        self.assertEqual(self.session.saved, [])

    def test_missing_previous_timestamp_can_refresh_without_fabrication(self) -> None:
        self.session.excel.timestamp = None
        with self.controller() as controller:
            result = controller.refresh(self.fo)
        self.assertIsNone(result.previous_refreshed_at)
        self.assertEqual(result.refreshed_at, datetime(2026, 11, 1, 8, 0, 2))

    def test_invalid_prior_timestamp_fails_without_refresh_or_save(self) -> None:
        self.session.excel.timestamp = True
        with self.controller() as controller:
            with self.assertRaises(ConfigurationError):
                controller.refresh(self.fo)
            self.assertEqual(controller.state, ControllerState.READY)
        self.assertEqual(self.commands(), [])
        self.assertEqual(self.session.saved, [])
        self.assertEqual(len(self.session.closed), 1)

    def test_unknown_prompt_failure_not_retried(self) -> None:
        self.session.excel.fail((AoMacro.SET_VAR,), 0, 1)
        with self.controller() as controller:
            with self.assertRaises(AoCommandError):
                controller.refresh(self.fo, True)
        self.assertEqual(sum(event[0] == AoMacro.SET_VAR for event in self.commands()), 1)

    def test_busy_retries_only_known_hresult(self) -> None:
        self.session.excel.fail(
            (AoMacro.EXEC_CMD, AoCmd.REFRESH_DATA),
            FakeComError(-2147418111),
        )
        with self.controller() as controller:
            controller.refresh(self.fo)
        self.assertGreaterEqual(self.clock.value, .1)
        self.assertEqual(self.session.excel.refresh_count, 2)

    def test_fatal_com_disconnect_poisoned(self) -> None:
        self.session.excel.fail((AoMacro.SET_VAR,), FakeComError(-2147417848, "secret-value"))
        with self.controller() as controller:
            with self.assertRaises(AoCommandError) as caught:
                controller.refresh(self.fo, True)
            self.assertEqual(controller.state, ControllerState.FAILED)
            self.assertNotIn("secret-value", str(caught.exception))
        self.assertEqual(self.session.saved, [])

    def test_deadline_during_prompt_cannot_claim_restoration(self) -> None:
        self.session.excel.advance_clock_on_prompt = 1
        with self.controller() as controller:
            with self.assertRaises(RefreshTimeoutError):
                controller.refresh(self.fo, True, timeout_minutes=.01)
            self.assertEqual(controller.state, ControllerState.FAILED)
        self.assertEqual(self.session.saved, [])

    def test_exact_configured_addin_only(self) -> None:
        self.options.addin_name = "Exact.Analysis.42"
        with self.controller():
            pass
        self.assertEqual(self.session.addins_requested, ["Exact.Analysis.42"])
        self.assertTrue(self.session.addin.Connect)

    def test_macro_unavailable_fails_enter_without_target(self) -> None:
        self.session.excel.fail((AoMacro.GET_PROPERTY,), RuntimeError("macro absent"))
        with self.assertRaises(ConnectionBindingError):
            with self.controller():
                self.fail("Must not enter")
        self.assertEqual(self.session.opened, [])
        self.assertEqual(self.session.events[-1], ("exit",))

    def test_datasource_readiness_is_not_macro_availability(self) -> None:
        self.session.excel.active = 0
        with self.controller() as controller:
            with self.assertRaises(RefreshTimeoutError):
                controller.refresh(self.fo, timeout_minutes=.01)
        self.assertEqual(self.commands(), [])
        self.assertEqual(len(self.session.closed), 1)

    def test_timestamp_validation_uses_workbook_date_system(self) -> None:
        self.session.excel.timestamp = 45000
        with self.controller() as controller:
            wb = FakeWorkbook(self.path, self.session.events)
            wb.Date1904 = True
            self.assertEqual(controller.get_last_refreshed_at(wb), datetime(2027, 3, 16))
            self.session.excel.timestamp = "not-a-date"
            with self.assertRaises(ConfigurationError):
                controller.get_last_refreshed_at(wb)
            self.assertEqual(controller.state, ControllerState.READY)

    def test_owned_property_workbook_closed_borrowed_workbook_not_closed(self) -> None:
        with self.controller() as controller:
            controller.check_workbook_prop(self.fo, WorkbookProperty.NAME)
            borrowed = FakeWorkbook(self.path, self.session.events)
            controller.check_workbook_prop(borrowed, WorkbookProperty.NAME)
        self.assertEqual(len(self.session.opened), 1)
        self.assertEqual(len(self.session.closed), 1)
        self.assertEqual(self.session.saved, [])

    def test_effective_filters_closes_owned_but_not_borrowed_workbook(self) -> None:
        with self.controller() as controller:
            self.assertEqual(controller.get_effective_filters(self.fo), 1)
            borrowed = FakeWorkbook(self.path, self.session.events)
            self.assertEqual(controller.get_effective_filters(borrowed), 1)
        self.assertEqual(len(self.session.opened), 1)
        self.assertEqual(len(self.session.closed), 1)
        self.assertEqual(self.session.saved, [])

    def test_standalone_set_variable_resolves_once(self) -> None:
        self.session.excel.fail((AoMacro.SET_VAR,), 0)
        self.session.excel.last_error = (32, "not ready")
        with self.controller() as controller:
            with patch("resin.ao.controller._field.resolve_field_dict", return_value={"P": "resolved"}) as resolve:
                controller.set_variable("P", "CURRENT_DAY")
                resolve.assert_called_once_with({"P": "CURRENT_DAY"})
        attempts = [event for event in self.commands() if event[0] == AoMacro.SET_VAR]
        self.assertEqual([event[2] for event in attempts], ["resolved", "resolved"])

    def test_strict_booleans_and_excel_errors(self) -> None:
        for value in (True, 1, 1.0):
            self.assertTrue(require_ao_bool(value, label="test"))
        for value in (False, 0, 0.0):
            self.assertFalse(require_ao_bool(value, label="test"))
        with self.assertRaises(ExcelComValueError):
            require_ao_bool(-2146826246, label="test")
        for value in ("0", "False", None, 2):
            with self.assertRaises(AoCommandError):
                require_ao_bool(value, label="test")

    def test_standalone_probe_uses_exact_addin(self) -> None:
        requested: list[str] = []

        def item(name: str) -> object:
            requested.append(name)
            return self.session.addin

        self.session.excel.COMAddIns = SimpleNamespace(Item=item)
        ensure_sap_ao_ready(
            self.session.excel, addin_name="Exact.Addin", clock=self.clock,
            sleep=self.clock.sleep, pump=self.clock.pump,
        )
        self.assertEqual(requested, ["Exact.Addin"])

    def test_options_are_side_effect_free_and_legacy_imports_share_identity(self) -> None:
        from resin.ao.Analysis import AoMacro as LegacyMacro
        from resin.ao.AnalysisController import Controller as LegacyController
        from resin.ao.Options import WorkbookOptions as LegacyOptions

        options = ControllerOptions.from_dict({
            "staging": str(self.root / "not-created"),
            "defaults": {"datasource": "CUSTOM_DS"},
            "refresh_cooldown_minutes": .5,
        })
        self.assertFalse(options.staging.exists())
        self.assertEqual(options.defaults.ds_alias, "CUSTOM_DS")
        self.assertEqual(options.refresh_cooldown_minutes, .5)
        self.assertEqual(ControllerOptions.from_dict(options.to_dict()), options)
        self.assertIs(LegacyMacro, AoMacro)
        self.assertIs(LegacyController, Controller)
        self.assertIs(LegacyOptions, WorkbookOptions)
        self.assertEqual(self.fo.id, "t(report)-f(report)-d(REPORT_DS)")
        self.assertEqual(self.fo.key, "report")

    def test_invalid_options_rejected_without_serializing_prompts(self) -> None:
        for value in (-1, float("nan"), True, "30"):
            with self.assertRaises(ConfigurationError):
                ControllerOptions(self.root / "stage", refresh_cooldown_minutes=value)
        with self.assertRaises(ConfigurationError):
            DefaultValueOptions("")
        with self.assertRaises(ConfigurationError):
            WorkbookOptions(self.path, prompts={1: "secret-value"})
        with self.assertRaises(ConfigurationError):
            ControllerOptions.from_dict({"staging": str(self.root), "defaults": []})
        with self.assertRaises(ConfigurationError):
            WorkbookOptions.from_dict({"filepath": str(self.path), "set_prompts": "true"})
        with self.assertRaises(ConfigurationError):
            ControllerOptions("https://example.invalid/staging")
        with self.assertRaises(ConfigurationError):
            ControllerOptions(self.path)


if __name__ == "__main__":
    unittest.main()
