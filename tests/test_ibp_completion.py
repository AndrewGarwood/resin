import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock

from pywintypes import com_error

from resin._workbook import (
    ConfigurationError, ControllerState, Deadline, PublicationDisposition,
    RefreshStatus, RefreshTimeoutError, parse_refresh_timestamp,
)
from resin.ibp.connection_options import ConnectionIdentity
from resin.ibp.controller import Controller
from resin.ibp.types import WorkbookProperty


def non_range_error():
    return com_error(
        -2147352567, "Exception occurred.",
        (0, "Microsoft Excel", "Application-defined or object-defined error",
         None, 0, -2146827284),
        None,
    )


class ScalarName:
    def __init__(self, value):
        self.Value = value

    @property
    def RefersToRange(self):
        raise non_range_error()


class IBPCompletionTests(unittest.TestCase):
    def setUp(self):
        self.time = 0.0
        self.deadline = Deadline(
            2, clock=lambda: self.time, sleep=self.advance,
            pump=lambda: None, poll_seconds=.25,
        )
        self.name = ScalarName("=46343.3888888889")
        self.worksheet = Mock()
        self.workbook = SimpleNamespace(
            Date1904=False, Names=Mock(return_value=self.name),
            Activate=Mock(), Worksheets=Mock(return_value=self.worksheet),
        )
        self.controller = Controller.__new__(Controller)
        self.controller._owner_thread = None
        self.controller._state = ControllerState.READY
        self.controller._session = SimpleNamespace(
            pid=12345, excel=SimpleNamespace(Ready=True, CalculationState=0),
        )
        self.controller.options = SimpleNamespace(
            stable_seconds=.5, cooldown_seconds=60,
        )
        self.controller.verbose = False

    def advance(self, seconds):
        self.time += seconds

    def transaction(self):
        return SimpleNamespace(
            wb=self.workbook, deadline=self.deadline, last_timestamp=None,
        )

    def test_scalar_name_refresh_returns_after_stable_timestamp_advance(self):
        txn = Mock(
            wb=self.workbook, deadline=self.deadline,
            last_timestamp=None, phase="open",
        )
        txn.set_phase.side_effect = lambda phase: setattr(txn, "phase", phase)
        txn.commit.return_value = PublicationDisposition.IN_PLACE
        operation = Mock()
        operation.__enter__ = Mock(return_value=txn)
        operation.__exit__ = Mock(return_value=False)
        self.controller.operation = Mock(return_value=operation)
        identity = ConnectionIdentity(name="Demand")
        self.controller._requested = Mock(return_value=identity)
        self.controller._ensure_binding = Mock(return_value=(identity, identity, True))
        self.controller._now = lambda: datetime(2026, 11, 20, 12)
        self.controller.api_config = SimpleNamespace(refresh_enabled=False)
        self.controller.ui = Mock()
        self.controller.ui.refresh.side_effect = lambda **kwargs: setattr(
            self.name, "Value", "=46346.445162037"
        )

        result = self.controller.refresh(Path(r"C:\Temp\planning.xlsm"))

        self.assertIs(result, txn.outcome.return_value)
        self.controller.ui.refresh.assert_called_once()
        txn.commit.assert_called_once_with()
        self.assertEqual(txn.outcome.call_args.args, (RefreshStatus.REFRESHED,))
        self.assertEqual(
            txn.outcome.call_args.kwargs["refreshed_at"],
            parse_refresh_timestamp(self.name.Value),
        )
        self.assertGreaterEqual(self.time, .5)
        self.assertLess(self.time, 2)

    def test_range_backed_timestamp_remains_supported(self):
        self.workbook.Names.return_value = SimpleNamespace(
            RefersToRange=SimpleNamespace(Value=datetime(2026, 11, 20, 10, 41, 2)),
        )

        self.assertEqual(
            self.controller._timestamp(self.workbook),
            datetime(2026, 11, 20, 10, 41, 2),
        )

    def test_blank_timestamp_remains_unavailable(self):
        self.name.Value = '=""'

        self.assertIsNone(self.controller._timestamp(self.workbook))

    def test_invalid_timestamp_is_reported_instead_of_polling(self):
        self.name.Value = '="not a timestamp"'

        with self.assertRaises(ConfigurationError):
            self.controller._wait_timestamp(self.transaction(), None)
        self.assertEqual(self.time, 0)

    def test_com_failure_is_not_swallowed_or_retried_as_a_scalar(self):
        failure = com_error(-2147417848, "Disconnected", None, None)
        name = Mock()
        type(name).RefersToRange = PropertyMock(side_effect=failure)
        scalar = PropertyMock()
        type(name).Value = scalar
        self.workbook.Names.return_value = name

        with self.assertRaises(com_error) as raised:
            self.controller._timestamp(self.workbook)

        self.assertIs(raised.exception, failure)
        scalar.assert_not_called()

    def test_unchanged_timestamp_respects_deadline(self):
        previous = parse_refresh_timestamp(self.name.Value)

        with self.assertRaises(RefreshTimeoutError):
            self.controller._wait_timestamp(self.transaction(), previous)

        self.assertEqual(self.time, 2)

    def test_missing_name_is_not_silently_treated_as_an_empty_timestamp(self):
        failure = non_range_error()
        self.workbook.Names.side_effect = failure

        with self.assertRaises(com_error) as raised:
            self.controller._timestamp(self.workbook)

        self.assertIs(raised.exception, failure)
        self.workbook.Names.assert_called_once_with(
            str(WorkbookProperty.REFRESH_TIMESTAMP)
        )


if __name__ == "__main__":
    unittest.main()
