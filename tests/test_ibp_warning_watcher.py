import unittest
from threading import Event
from unittest.mock import Mock, patch

from resin.ibp.controller import Controller
from resin.ibp.binding import BindingObservation, BindingState
from resin.ibp.connection_options import ConnectionIdentity
from resin.ibp.warning_watcher import version_warning_watcher


class VersionWarningWatcherTests(unittest.TestCase):
    def make_dialog(self, text=None):
        message = Mock()
        message.window_text.return_value = text or (
            "The version of the SAP IBP, add-in for Microsoft Excel (2502.4.0) "
            "is lower than the required version (2505.2.0). Please update."
        )
        message.friendly_class_name.return_value = "Static"
        button = Mock()
        button.window_text.return_value = "&OK"
        button.friendly_class_name.return_value = "Button"
        button.is_visible.return_value = True
        button.is_enabled.return_value = True
        dialog = Mock()
        dialog.descendants.return_value = [message, button]
        return dialog, button

    def test_warning_is_dismissed_while_connect_is_blocked(self):
        dialog, button = self.make_dialog()
        connecting = Event()
        dismissed = Event()
        button.click.side_effect = dismissed.set
        desktop = Mock()
        desktop.windows.side_effect = lambda **kwargs: (
            [dialog] if connecting.is_set() else []
        )
        controller = Mock()
        controller.session.pid = 12345
        requested = ConnectionIdentity(name="Demand")
        controller._requested.return_value = requested
        controller._verifier = None
        controller._observe.return_value = BindingObservation(
            BindingState.VALID, requested
        )

        def connect(name):
            connecting.set()
            self.assertTrue(dismissed.wait(2), "Connect remained blocked by warning")
            return True

        controller.ibp.Connect.side_effect = connect
        with patch("resin.ibp.warning_watcher.Desktop", return_value=desktop):
            result = Controller._ensure_binding(controller, Mock(), Mock(), Mock())

        self.assertEqual(result, (requested, requested, True))
        controller.ibp.Connect.assert_called_once_with("Demand")
        button.click.assert_called_once_with()
        desktop.windows.assert_called_with(
            title="SAP IBP: Warning", process=12345, visible_only=True,
        )

    def test_absent_warning_is_optional_and_thread_stops(self):
        polled = Event()
        desktop = Mock()

        def windows(**kwargs):
            polled.set()
            return []

        desktop.windows.side_effect = windows
        with patch("resin.ibp.warning_watcher.Desktop", return_value=desktop):
            with version_warning_watcher(12345) as watcher:
                self.assertTrue(polled.wait(2))
        self.assertFalse(watcher.handled)
        self.assertIsNone(watcher.error)
        self.assertTrue(watcher.done.is_set())
        assert watcher.thread is not None
        self.assertFalse(watcher.thread.is_alive())

    def test_unrelated_warning_is_not_acknowledged(self):
        dialog, button = self.make_dialog("The server is unavailable.")
        inspected = Event()
        dialog.descendants.side_effect = lambda: (
            inspected.set() or dialog.descendants.return_value
        )
        desktop = Mock()
        desktop.windows.return_value = [dialog]
        with patch("resin.ibp.warning_watcher.Desktop", return_value=desktop):
            with version_warning_watcher(12345) as watcher:
                self.assertTrue(inspected.wait(2))
        button.click.assert_not_called()
        self.assertFalse(watcher.handled)

    def test_worker_failure_is_reported(self):
        failure = OSError("Enumeration failed")
        desktop = Mock()
        desktop.windows.side_effect = failure
        with patch("resin.ibp.warning_watcher.Desktop", return_value=desktop):
            with patch("resin.ibp.warning_watcher.mlog"):
                with self.assertRaisesRegex(RuntimeError, "watcher failed") as raised:
                    with version_warning_watcher(12345) as watcher:
                        self.assertTrue(watcher.done.wait(2))
        self.assertIs(raised.exception.__cause__, failure)

    def test_connect_failure_is_preserved_and_watcher_stops(self):
        watcher = None
        with patch("resin.ibp.warning_watcher.Desktop") as desktop:
            desktop.return_value.windows.return_value = []
            with self.assertRaisesRegex(ValueError, "Connect failed"):
                with version_warning_watcher(12345) as watcher:
                    raise ValueError("Connect failed")
        assert watcher is not None
        self.assertTrue(watcher.done.is_set())
        assert watcher.thread is not None
        self.assertFalse(watcher.thread.is_alive())


if __name__ == "__main__":
    unittest.main()
