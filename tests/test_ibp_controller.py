"""IBP contract tests. All COM, sessions, clocks and UI are fakes."""
from __future__ import annotations

import shutil
import unittest
import warnings
from datetime import datetime, timedelta
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from resin._workbook import (
    ConfigurationError, ConnectionBindingError, ControllerState, Deadline,
    PublicationDisposition, RefreshStatus, RefreshTimeoutError, WorkbookControllerError,
)
from resin.ibp import (
    BindingObservation, BindingState, ConnectionIdentity, ConnectionMode,
    ConnectionOptions, Controller, ControllerOptions, IbpConnectionError, IbpFilter,
    IbpFilterOperator, RefreshMethod, RibbonRefreshUI,
    WorkbookOptions, WorkbookProperty,
)

STAMP = datetime(2026, 1, 1, 12)
IDENTITY = ConnectionIdentity("Demand", "PA", "https://example.invalid", "connection-1")


class FakeClock:
    def __init__(self):
        self.value = 0.0
        self.after_sleep = None

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds
        if self.after_sleep:
            self.after_sleep(self.value)


class FakeName:
    def __init__(self, wb, name, attr):
        self.wb, self.Name, self.attr = wb, name, attr
        self.RefersTo = "=Sheet1!A1"

    @property
    def RefersToRange(self):
        return SimpleNamespace(Value=getattr(self.wb, self.attr))


class FakeWorksheet:
    def __init__(self, wb):
        self.wb = wb

    def Activate(self):
        self.wb.Activate()


class FakeWorkbook:
    ReadOnly = False
    Date1904 = False

    def __init__(self, session, path):
        self.session, self.path = session, Path(path)
        self.FullName = str(path)
        self.connection_name = "Demand"
        self.stamp = STAMP
        self.binding = BindingState.MISSING
        self.identity = IDENTITY
        self.closed = False
        self.Names = [
            FakeName(self, WorkbookProperty.CONNECTION_NAME, "connection_name"),
            FakeName(self, WorkbookProperty.REFRESH_TIMESTAMP, "stamp"),
        ]

    def Activate(self):
        if self.closed:
            raise AssertionError("using closed fake workbook")
        self.session.active = self

    def Worksheets(self, name):
        if name not in ("Demand View", 1):
            raise KeyError("missing worksheet")
        return FakeWorksheet(self)


class FakeAddin:
    def __init__(self, session):
        self.session = session
        self.connect_calls = []
        self.refresh_calls = 0
        self.connect_result = True
        self.api_error = None
        self.advance = True
        self.connect_hook = None

    def Connect(self, name):
        self.connect_calls.append(name)
        self.session.events.append(("connect", self.session.active.path.name))
        wb = self.session.active
        wb.binding = BindingState.VALID
        wb.connection_name = name
        if self.connect_hook:
            self.connect_hook(wb)
        return self.connect_result

    def GetConnections(self, ws):
        return {"binding": ws.wb.binding, "identity": ws.wb.identity}

    def Refresh(self):
        self.refresh_calls += 1
        if self.api_error:
            raise self.api_error
        if self.advance:
            self.session.active.stamp += timedelta(minutes=1)
        return None


class FakeSession:
    pid = 12345

    def __init__(self):
        self.excel = SimpleNamespace(CalculationState=0, Ready=True)
        self.addin = FakeAddin(self)
        self.events = []
        self.opened = []
        self.active = None
        self.configure = None
        self.saved = []
        self.added_paths = []

    def __enter__(self):
        self.events.append(("enter",))
        return self

    def __exit__(self, *args):
        self.events.append(("exit",))
        for wb in self.opened:
            wb.closed = True

    def get_com_addin(self, name):
        return SimpleNamespace(Connect=True, Object=self.addin)

    def open_workbook(self, path):
        wb = FakeWorkbook(self, path)
        if self.configure:
            self.configure(wb)
        self.opened.append(wb)
        self.events.append(("open", Path(path).name))
        return wb

    def add_workbook(self, path):
        self.added_paths.append(Path(path))
        Path(path).write_bytes(b"fake anchor")
        return self.open_workbook(path)

    def save_workbook(self, wb, timeout):
        if wb.closed:
            raise AssertionError("saving closed workbook")
        self.saved.append(wb)
        wb.path.write_bytes(b"fake refreshed workbook")
        self.events.append(("save", wb.path.name))

    def close_workbook(self, wb, save_changes=False):
        if save_changes:
            raise AssertionError("unexpected implicit save")
        if wb.closed:
            raise AssertionError("duplicate close")
        wb.closed = True
        self.events.append(("close", wb.path.name))


class FakeUI:
    def __init__(self):
        self.calls = []
        self.advance = True
        self.error = None

    def refresh(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        if self.advance:
            kwargs["workbook"].stamp += timedelta(minutes=1)


def verify_binding(*, workbook, worksheet, requested, connections, connect_result):
    return BindingObservation(
        connections["binding"],
        connections["identity"] if connections["binding"] == BindingState.VALID else None,
    )


class IBPControllerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent / f".ibp-test-{uuid4().hex}"
        self.root.mkdir()
        self.path = self.root / "target.xlsx"
        self.path.write_bytes(b"fake workbook")
        self.clock, self.session, self.ui = FakeClock(), FakeSession(), FakeUI()
        self.real_session_guard = patch(
            "resin._workbook.lifecycle.default_session_factory",
            side_effect=AssertionError("real Excel is forbidden"),
        )
        self.real_session_guard.start()

    def tearDown(self):
        self.real_session_guard.stop()
        shutil.rmtree(self.root)

    def controller(self, *, conn=None, mode=ConnectionMode.WORKBOOK, seed=None, **kwargs):
        kwargs.setdefault("stable_seconds", .5)
        kwargs.setdefault("poll_seconds", .25)
        kwargs.setdefault("staging_policy", "never")
        return Controller(
            ControllerOptions(
                self.root / "stage", conn or ConnectionOptions(name="Demand"),
                connection_mode=mode, anchor_seed=seed,
            ),
            session_factory=lambda: self.session, clock=self.clock, sleep=self.clock.sleep,
            pump=lambda: None, now=lambda: STAMP + timedelta(days=1),
            ui=self.ui, **kwargs,
        )

    def test_default_workbook_connects_and_returns_actual_timestamp(self):
        with self.controller() as controller:
            outcome = controller.refresh(self.path, method=RefreshMethod.API)
            self.assertEqual(controller.options.connection_mode, ConnectionMode.WORKBOOK)
            self.assertEqual(outcome.status, RefreshStatus.REFRESHED)
            self.assertEqual(outcome.refreshed_at, STAMP + timedelta(minutes=1))
            self.assertEqual(outcome.publication, PublicationDisposition.IN_PLACE)
            self.assertTrue(outcome.details.connect_called)
            self.assertFalse(outcome.details.binding_reused)
        self.assertEqual(self.session.addin.connect_calls, ["Demand"])
        self.assertEqual(self.session.addin.refresh_calls, 1)
        self.assertGreaterEqual(self.clock.value, .5)
        self.assertTrue(self.session.opened[0].closed)

    def test_ui_uses_same_timestamp_completion_and_owned_path(self):
        with self.controller() as controller:
            result = controller.refresh(self.path)
        self.assertEqual(result.refreshed_at, STAMP + timedelta(minutes=1))
        self.assertEqual(self.ui.calls[0]["pid"], self.session.pid)
        self.assertEqual(self.ui.calls[0]["path"], self.path.resolve())
        self.assertEqual(self.session.addin.refresh_calls, 0)

    def test_staged_ui_uses_staged_identity_and_publishes_only_after_completion(self):
        with self.controller(staging_policy="always") as controller:
            result = controller.refresh(self.path)
        staged = self.ui.calls[0]["path"]
        self.assertNotEqual(staged, self.path.resolve())
        self.assertEqual(staged.name, self.path.name)
        self.assertFalse(staged.exists())
        self.assertEqual(result.publication, PublicationDisposition.PUBLISHED)
        self.assertEqual(self.path.read_bytes(), b"fake refreshed workbook")

    def test_cooldown_closes_target_without_connect_or_save(self):
        self.session.configure = lambda wb: setattr(wb, "stamp", STAMP + timedelta(days=1))
        with self.controller() as controller:
            result = controller.refresh(self.path)
        self.assertEqual(result.status, RefreshStatus.SKIPPED_COOLDOWN)
        self.assertIsNone(result.details.observed_connection)
        self.assertIsNone(result.details.binding_reused)
        self.assertEqual(result.publication, PublicationDisposition.NOT_ATTEMPTED)
        self.assertFalse(self.session.saved)
        self.assertFalse(self.session.addin.connect_calls)
        self.assertTrue(self.session.opened[0].closed)

    def test_force_overrides_cooldown(self):
        self.session.configure = lambda wb: setattr(wb, "stamp", STAMP + timedelta(days=1))
        with self.controller() as controller:
            result = controller.refresh(self.path, force=True, method=RefreshMethod.API)
        self.assertEqual(result.status, RefreshStatus.REFRESHED)

    def test_legacy_skip_adapter_retains_placeholder(self):
        self.session.configure = lambda wb: setattr(wb, "stamp", STAMP + timedelta(days=1))
        with self.controller() as controller, warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = controller.refresh_workbook(WorkbookOptions(self.path))
        self.assertEqual(result.conn_name, "<No connection made>")
        self.assertEqual(result.conn_id, "<No connection made>")
        self.assertTrue(any(item.category is DeprecationWarning for item in caught))

    def test_proven_binding_reused_without_connect(self):
        self.session.configure = lambda wb: setattr(wb, "binding", BindingState.VALID)
        with self.controller(binding_verifier=verify_binding) as controller:
            result = controller.refresh(self.path, method=RefreshMethod.API)
        self.assertTrue(result.details.binding_reused)
        self.assertFalse(self.session.addin.connect_calls)
        self.assertEqual(result.details.observed_connection, IDENTITY)

    def test_expired_binding_reconnects_only_once_before_refresh(self):
        self.session.configure = lambda wb: setattr(wb, "binding", BindingState.EXPIRED)
        with self.controller(binding_verifier=verify_binding) as controller:
            result = controller.refresh(self.path, method=RefreshMethod.API)
        self.assertTrue(result.details.connect_called)
        self.assertEqual(self.session.addin.connect_calls, ["Demand"])
        self.assertEqual(self.session.addin.refresh_calls, 1)

    def test_failed_reconnect_is_not_retried(self):
        self.session.addin.connect_hook = lambda wb: setattr(wb, "binding", BindingState.EXPIRED)
        with self.controller(binding_verifier=verify_binding) as controller:
            with self.assertRaises(ConnectionBindingError):
                controller.refresh(self.path, method=RefreshMethod.API)
        self.assertEqual(self.session.addin.connect_calls, ["Demand"])
        self.assertEqual(self.session.addin.refresh_calls, 0)
        self.assertFalse(self.session.saved)

    def test_metadata_mismatch_rejected_before_connect(self):
        self.session.configure = lambda wb: setattr(wb, "connection_name", "Other")
        with self.controller() as controller:
            with self.assertRaises(ConnectionBindingError):
                controller.refresh(self.path)
        self.assertFalse(self.session.addin.connect_calls)

    def test_planning_area_mismatch_rejected_before_connect(self):
        def configure(wb):
            wb.binding = BindingState.VALID
            wb.identity = ConnectionIdentity("Demand", "OTHER", IDENTITY.server_url, IDENTITY.id)
        self.session.configure = configure
        conn = ConnectionOptions("Demand", "PA", IDENTITY.server_url, id=IDENTITY.id)
        with self.controller(conn=conn, binding_verifier=verify_binding) as controller:
            with self.assertRaises(ConnectionBindingError):
                controller.refresh(self.path)
        self.assertFalse(self.session.addin.connect_calls)

    def test_non_name_identity_requires_verifier(self):
        with self.assertRaises(ConfigurationError):
            self.controller(conn=ConnectionOptions("Demand", planning_area="PA"))
        with self.assertRaises(ConfigurationError):
            self.controller(conn=ConnectionOptions("Demand", server_url="https://example.invalid"))

    def test_invalid_verifier_result_rejected(self):
        with self.controller(binding_verifier=lambda **kwargs: True) as controller:
            with self.assertRaises(ConnectionBindingError):
                controller.refresh(self.path)
        self.assertFalse(self.session.addin.refresh_calls)

    def test_invalid_connections_shape_is_sanitized_binding_error(self):
        with patch.object(self.session.addin, "GetConnections", return_value="unknown shape"):
            with self.controller(binding_verifier=verify_binding) as controller:
                with self.assertRaises(ConnectionBindingError) as caught:
                    controller.refresh(self.path)
        self.assertNotIn("unknown shape", str(caught.exception))
        self.assertFalse(self.session.addin.refresh_calls)

    def test_verifier_must_prove_configured_non_name_identity(self):
        def incomplete(**kwargs):
            return BindingObservation(BindingState.VALID, ConnectionIdentity("Demand"))
        with self.controller(
            conn=ConnectionOptions("Demand", planning_area="PA"), binding_verifier=incomplete,
        ) as controller:
            with self.assertRaises(ConnectionBindingError):
                controller.refresh(self.path)

    def test_invalid_connect_result_rejected_without_verifier(self):
        for result in (None, False, "connected", {}, 2):
            self.session.addin.connect_result = result
            with self.controller() as controller:
                with self.assertRaises(ConnectionBindingError):
                    controller.refresh(self.path)
        self.assertEqual(self.session.addin.refresh_calls, 0)

    def test_api_failure_never_falls_back_or_replays(self):
        self.session.addin.api_error = RuntimeError("API disabled")
        with self.controller() as controller:
            with self.assertRaises(WorkbookControllerError):
                controller.refresh(self.path, method=RefreshMethod.API)
            self.assertEqual(controller.state, ControllerState.FAILED)
        self.assertFalse(self.ui.calls)
        self.assertEqual(self.session.addin.refresh_calls, 1)
        self.assertFalse(self.session.saved)

    def test_unchanged_timestamp_times_out_without_save_or_refresh_replay(self):
        self.session.addin.advance = False
        with self.controller() as controller:
            with self.assertRaises(RefreshTimeoutError):
                controller.refresh(self.path, timeout_minutes=.02, method=RefreshMethod.API)
        self.assertLessEqual(self.clock.value, 1.2)
        self.assertEqual(self.session.addin.refresh_calls, 1)
        self.assertFalse(self.session.saved)
        self.assertTrue(self.session.opened[-1].closed)

    def test_timestamp_stability_restarts_after_regression(self):
        def on_sleep(value):
            wb = self.session.active
            if value == .25:
                wb.stamp = STAMP
            if value >= .5:
                wb.stamp = STAMP + timedelta(minutes=2)
        self.clock.after_sleep = on_sleep
        with self.controller() as controller:
            result = controller.refresh(self.path, method=RefreshMethod.API)
        self.assertEqual(result.refreshed_at, STAMP + timedelta(minutes=2))
        self.assertGreaterEqual(self.clock.value, 1)

    def test_connect_timestamp_change_is_not_refresh_completion(self):
        self.session.addin.connect_hook = lambda wb: setattr(wb, "stamp", STAMP + timedelta(minutes=1))
        self.session.addin.advance = False
        with self.controller() as controller:
            with self.assertRaises(RefreshTimeoutError):
                controller.refresh(self.path, timeout_minutes=.02, method=RefreshMethod.API)
        self.assertFalse(self.session.saved)

    def test_connect_cannot_erase_previous_completion_baseline(self):
        self.session.addin.connect_hook = lambda wb: setattr(wb, "stamp", None)
        self.ui.advance = False
        self.clock.after_sleep = lambda value: setattr(self.session.active, "stamp", STAMP)
        with self.controller() as controller:
            with self.assertRaises(RefreshTimeoutError):
                controller.refresh(self.path, timeout_minutes=.02)
        self.assertFalse(self.session.saved)

    def test_missing_timestamp_requires_real_advanced_timestamp(self):
        self.session.configure = lambda wb: setattr(wb, "stamp", None)
        self.ui.advance = False
        self.clock.after_sleep = lambda value: setattr(
            self.session.active, "stamp", STAMP + timedelta(minutes=2)
        )
        with self.controller() as controller:
            result = controller.refresh(self.path)
        self.assertIsNone(result.previous_refreshed_at)
        self.assertEqual(result.refreshed_at, STAMP + timedelta(minutes=2))

    def test_property_helpers_close_only_workbooks_they_open(self):
        with self.controller() as controller:
            value = controller.get_workbook_property(
                WorkbookOptions(self.path), WorkbookProperty.CONNECTION_NAME,
                lambda value: value.upper(),
            )
            self.assertEqual(value, "DEMAND")
            self.assertTrue(self.session.opened[-1].closed)
            self.assertEqual(controller.get_last_refreshed_at(self.path), STAMP)
            self.assertTrue(self.session.opened[-1].closed)
        self.assertFalse(self.session.saved)

    def test_borrowed_session_explicitly_rejected(self):
        controller = self.controller()
        with self.assertRaises(ConfigurationError):
            with controller.bind_session(self.session):
                self.fail("unsafe binding was accepted")
        self.assertFalse(self.session.events)

    def test_anchor_requires_explicit_verifier_and_connection_name(self):
        with self.assertRaises(ConfigurationError):
            self.controller(mode=ConnectionMode.ANCHOR)
        with self.assertRaises(ConfigurationError):
            self.controller(
                mode=ConnectionMode.ANCHOR, conn=ConnectionOptions(),
                binding_verifier=verify_binding,
            )
        self.assertFalse(self.session.events)

    def test_anchor_eager_connect_and_survives_two_target_closes(self):
        second = self.root / "second.xlsx"
        second.write_bytes(b"fake second")
        with self.controller(mode=ConnectionMode.ANCHOR, binding_verifier=verify_binding) as controller:
            anchor = self.session.opened[0]
            self.assertEqual(len(self.session.addin.connect_calls), 1)
            self.assertEqual(self.session.added_paths, [anchor.path])
            self.assertTrue(anchor.path.exists())
            controller.refresh(self.path, method=RefreshMethod.API)
            self.assertFalse(anchor.closed)
            controller.refresh(second, method=RefreshMethod.API)
            self.assertFalse(anchor.closed)
        self.assertTrue(anchor.closed)
        self.assertFalse(anchor.path.exists())
        close_index = self.session.events.index(("close", anchor.path.name))
        exit_index = self.session.events.index(("exit",))
        self.assertLess(close_index, exit_index)
        self.assertEqual(len(self.session.addin.connect_calls), 3)

    def test_anchor_valid_targets_reuse_without_redundant_connect(self):
        second = self.root / "second.xlsx"
        second.write_bytes(b"second")
        self.session.configure = lambda wb: setattr(wb, "binding", BindingState.VALID)
        with self.controller(mode=ConnectionMode.ANCHOR, binding_verifier=verify_binding) as controller:
            anchor = self.session.opened[0]
            first_result = controller.refresh(self.path, method=RefreshMethod.API)
            second_result = controller.refresh(second, method=RefreshMethod.API)
            self.assertFalse(anchor.closed)
        self.assertTrue(first_result.details.binding_reused)
        self.assertTrue(second_result.details.binding_reused)
        self.assertEqual(self.session.addin.connect_calls, ["Demand"])
        self.assertEqual(self.session.addin.refresh_calls, 2)

    def test_seed_is_private_copy_and_never_saved_back(self):
        seed = self.root / "seed.xlsm"
        seed.write_bytes(b"private seed content")
        with self.controller(
            mode=ConnectionMode.ANCHOR, seed=seed, binding_verifier=verify_binding,
        ):
            anchor = self.session.opened[0]
            self.assertNotEqual(anchor.path, seed)
            self.assertEqual(anchor.path.suffix, ".xlsm")
            self.assertTrue(anchor.path.exists())
        self.assertEqual(seed.read_bytes(), b"private seed content")
        self.assertFalse(anchor.path.exists())
        self.assertFalse(self.session.saved)
        self.assertFalse(self.session.added_paths)

    def test_anchor_entry_failure_unwinds_without_workbook_fallback(self):
        self.session.addin.connect_hook = lambda wb: setattr(wb, "binding", BindingState.EXPIRED)
        with self.assertRaises(ConnectionBindingError):
            with self.controller(mode=ConnectionMode.ANCHOR, binding_verifier=verify_binding):
                self.fail("entry should fail")
        self.assertEqual(len(self.session.opened), 1)
        self.assertTrue(self.session.opened[0].closed)
        self.assertFalse(self.session.opened[0].path.exists())
        self.assertEqual(self.session.events[-1], ("exit",))
        self.assertEqual(self.session.addin.connect_calls, ["Demand"])

    def test_anchor_unsupported_blank_does_not_implicitly_try_seed(self):
        with patch.object(self.session, "add_workbook", side_effect=RuntimeError("unsupported blank")):
            with self.assertRaises(RuntimeError):
                with self.controller(mode=ConnectionMode.ANCHOR, binding_verifier=verify_binding):
                    self.fail("blank creation must fail")
        self.assertFalse(self.session.opened)
        self.assertEqual(self.session.events[-1], ("exit",))

    def test_seed_copy_deadline_checked_before_open_and_created_copy_cleaned(self):
        seed = self.root / "seed.xlsx"
        seed.write_bytes(b"seed")
        original_copy = shutil.copy2
        copied = []

        def slow_copy(source, destination):
            copied.append(Path(destination))
            result = original_copy(source, destination)
            self.clock.value += 2
            return result

        with patch("resin.ibp.controller.shutil.copy2", side_effect=slow_copy):
            with self.assertRaises(RefreshTimeoutError):
                with self.controller(
                    mode=ConnectionMode.ANCHOR, seed=seed,
                    binding_verifier=verify_binding, startup_timeout_seconds=1,
                ):
                    self.fail("expired seed copy must not enter")
        self.assertFalse(self.session.opened)
        self.assertEqual(len(copied), 1)
        self.assertFalse(copied[0].exists())
        self.assertEqual(seed.read_bytes(), b"seed")
        self.assertEqual(self.session.events[-1], ("exit",))

    def test_anchor_file_removed_when_open_or_add_raises_after_creation(self):
        seed = self.root / "seed.xlsx"
        seed.write_bytes(b"seed")
        for use_seed in (False, True):
            created = []

            def failing_create(path):
                path = Path(path)
                path.write_bytes(b"created before COM failure")
                created.append(path)
                raise RuntimeError("fake open/add failure")

            method = "open_workbook" if use_seed else "add_workbook"
            with patch.object(self.session, method, side_effect=failing_create):
                with self.assertRaisesRegex(RuntimeError, "fake open/add failure"):
                    with self.controller(
                        mode=ConnectionMode.ANCHOR, seed=seed if use_seed else None,
                        binding_verifier=verify_binding,
                    ):
                        self.fail("partial entry must fail")
            self.assertEqual(len(created), 1)
            self.assertFalse(created[0].exists())
            self.assertEqual(self.session.events[-1], ("exit",))
        self.assertEqual(seed.read_bytes(), b"seed")

    def test_compatibility_models_alias_and_import_modules(self):
        from resin.ibp.Ibp import IbpFilter as CompatFilter, _IbpFilter
        from resin.ibp.IbpController import Controller as CompatController
        self.assertIs(IbpConnectionError, ConnectionBindingError)
        self.assertIs(CompatFilter, IbpFilter)
        self.assertIs(CompatController, Controller)
        self.assertEqual(list(IbpFilterOperator), [])
        data: _IbpFilter = {"attr": "Product", "value": "", "operator": "EQ"}
        self.assertEqual(IbpFilter.from_dict(data), IbpFilter("Product", "", "EQ"))
        with self.assertRaises(ConfigurationError):
            IbpFilter.from_dict({"attr": "Product", "value": "P"})
        with self.assertRaises(ConfigurationError):
            IbpFilter.from_dict({"attr": "Product", "value": 1, "operator": "EQ"})

    def test_options_module_spellings_share_module_and_class_identity(self):
        lowercase = import_module("resin.ibp.options")
        historical = import_module("resin.ibp.Options")
        self.assertIs(lowercase, historical)
        for name in ("ConnectionOptions", "ControllerOptions", "RefreshInfo", "WorkbookOptions"):
            self.assertIs(getattr(lowercase, name), getattr(historical, name))
        self.assertIs(lowercase.WorkbookOptions, WorkbookOptions)
        self.assertIs(historical.ControllerOptions, ControllerOptions)

    def test_filter_configuration_parses_but_refresh_explicitly_rejects(self):
        options = WorkbookOptions.from_dict({
            "path": str(self.path),
            "filters": [{"attr": "Product", "value": "P1", "operator": "EQ"}],
        })
        self.assertEqual(options.filters, [IbpFilter("Product", "P1", "EQ")])
        controller = self.controller()
        with self.assertRaisesRegex(ConfigurationError, "filter mutation is unsupported"):
            controller.refresh(options)
        self.assertFalse(self.session.events)

    def test_staging_options_used_unless_explicit_constructor_override(self):
        options = ControllerOptions.from_dict({
            "staging": str(self.root / "stage"), "connection": {"name": "Demand"},
            "staging_policy": "auto", "stage_roots": [str(self.root)],
        })
        inherited = Controller(options, session_factory=lambda: self.session)
        self.assertEqual(inherited.staging_policy, "auto")
        self.assertEqual(inherited.stage_roots, (self.root.resolve(),))
        overridden = Controller(
            options, staging_policy="never", stage_roots=(),
            session_factory=lambda: self.session,
        )
        self.assertEqual(overridden.staging_policy, "never")
        self.assertEqual(overridden.stage_roots, ())
        with self.assertRaises(ConfigurationError):
            ControllerOptions(self.root / "stage", ConnectionOptions("Demand"), staging_policy="invalid")

    def test_options_parsing_is_side_effect_free_and_preserves_metadata(self):
        options = ControllerOptions.from_dict({
            "staging": str(self.root / "not-created"),
            "connection": {"name": "Demand"}, "refresh_cooldown_minutes": .5,
        })
        self.assertFalse(options.staging.exists())
        self.assertEqual(options.refresh_cooldown_minutes, .5)
        wbo = WorkbookOptions.from_dict({
            "path": str(self.path), "data_origin": "B3", "search_headers": ["Product"],
        })
        self.assertEqual(wbo.header_origin.excel_address, "B2")
        self.assertEqual(wbo.info_addr.excel_address, "B1")

    def test_unsupported_filters_writeback_and_invalid_durations_rejected(self):
        with self.assertRaises(ConfigurationError):
            WorkbookOptions(self.path, filters=[{"attr": "x"}])
        with self.assertRaises(ConfigurationError):
            WorkbookOptions(self.path, refresh_only=False)
        with self.assertRaises(ConfigurationError):
            self.controller(stable_seconds=True)


class RibbonRefreshTests(unittest.TestCase):
    def test_reuses_pid_scoped_helpers_and_scopes_refresh_to_ribbon(self):
        window, ribbon, tab, button = [SimpleNamespace() for _ in range(4)]
        window.set_focus = lambda: None
        clicks = []
        tab.click_input = lambda: clicks.append("tab")
        button.click_input = lambda: clicks.append("refresh")
        wb = SimpleNamespace(Activate=lambda: None)
        ws = SimpleNamespace(Activate=lambda: None)
        clock = FakeClock()
        deadline = Deadline(10, clock=clock, sleep=clock.sleep, pump=lambda: None)
        with patch("resin.ibp.controller.winauto.attach_to_process_window", return_value=(None, window)) as attach:
            with patch(
                "resin.ibp.controller.winauto.find_available_control", side_effect=[ribbon, tab, button],
            ) as find:
                RibbonRefreshUI().refresh(
                    workbook=wb, worksheet=ws, pid=123, path=Path("target.xlsx"),
                    backend="uia", deadline=deadline,
                )
        self.assertEqual(attach.call_args.args, (123, "target.xlsx"))
        self.assertTrue(attach.call_args.kwargs["require_unique"])
        self.assertIs(find.call_args_list[1].args[0], ribbon)
        self.assertIs(find.call_args_list[2].args[0], ribbon)
        self.assertTrue(all(call.kwargs["require_unique"] for call in find.call_args_list))
        self.assertEqual(clicks, ["tab", "refresh"])

    def test_ambiguous_control_failure_does_not_click(self):
        window = SimpleNamespace(set_focus=lambda: None)
        deadline = Deadline(10, pump=lambda: None)
        with patch("resin.ibp.controller.winauto.attach_to_process_window", return_value=(None, window)):
            with patch(
                "resin.ibp.controller.winauto.find_available_control",
                side_effect=RuntimeError("Multiple controls"),
            ):
                with self.assertRaisesRegex(RuntimeError, "Multiple controls"):
                    RibbonRefreshUI().refresh(
                        workbook=SimpleNamespace(Activate=lambda: None),
                        worksheet=SimpleNamespace(Activate=lambda: None),
                        pid=123, path=Path("target.xlsx"), backend="uia", deadline=deadline,
                    )


if __name__ == "__main__":
    unittest.main()
