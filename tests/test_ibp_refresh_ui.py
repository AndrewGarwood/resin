import re
import unittest
from unittest.mock import Mock, call, patch

from pywinauto.timings import TimeoutError

from resin._workbook import Deadline
from resin.ibp.refresh_ui import RibbonRefreshUI
from resin.utils import winauto


class RibbonRefreshUITests(unittest.TestCase):
    def setUp(self):
        self.workbook = Mock()
        self.workbook.Name = "Planning [test].xlsm"
        self.worksheet = Mock()
        self.app = Mock()
        self.window = self.app.window.return_value
        self.tab = Mock()
        self.button = Mock()
        self.window.child_window.side_effect = [self.tab, self.button]
        self.deadline = Deadline(10, clock=lambda: 0, pump=lambda: None)
        self.connect = patch(
            "resin.ibp.refresh_ui.winauto.connect_application",
            return_value=self.app,
        )
        self.connect_mock = self.connect.start()
        self.addCleanup(self.connect.stop)
        legacy_find = patch(
            "resin.ibp.refresh_ui.winauto.find_window",
            side_effect=[self.window, winauto.AutomationError(
                "SAP IBP is not a native HWND control"
            )],
        )
        legacy_find.start()
        self.addCleanup(legacy_find.stop)

    def refresh(self, **kwargs):
        RibbonRefreshUI().refresh(
            self.workbook, self.worksheet, 12345,
            deadline=self.deadline, **kwargs,
        )

    def test_uia_tab_and_refresh_are_scoped_to_the_workbook(self):
        events = Mock()
        events.attach_mock(self.workbook.Activate, "workbook_activate")
        events.attach_mock(self.worksheet.Activate, "worksheet_activate")
        events.attach_mock(self.window.set_focus, "focus")
        events.attach_mock(self.tab.click_input, "tab_click")
        events.attach_mock(self.button.click_input, "refresh_click")

        self.refresh()

        self.connect_mock.assert_called_once_with(
            12345, backend=winauto.DesktopBackend.UIA, timeout_seconds=10,
        )
        self.app.window.assert_called_once_with(
            title_re=rf"^{re.escape(self.workbook.Name)}.*",
        )
        self.assertEqual(self.window.child_window.call_args_list, [
            call(title="SAP IBP", control_type="TabItem"),
            call(title="Refresh", control_type="Button"),
        ])
        self.assertEqual(events.mock_calls, [
            call.workbook_activate(), call.worksheet_activate(),
            call.focus(), call.tab_click(), call.refresh_click(),
        ])
        for control in (self.window, self.tab, self.button):
            control.wait.assert_called_once_with("ready", timeout=10)
            control.wait_for_idle.assert_not_called()

    def test_supplied_handle_selects_the_workbook_not_just_the_process(self):
        self.refresh(workbook_handle=456)

        self.app.window.assert_called_once_with(handle=456)

    def test_delayed_ribbon_readiness_uses_the_remaining_deadline(self):
        now = [0.0]
        self.deadline = Deadline(10, clock=lambda: now[0], pump=lambda: None)
        self.tab.wait.side_effect = lambda *a, **k: now.__setitem__(0, 3.0)

        self.refresh()

        self.button.wait.assert_called_once_with("ready", timeout=7)
        self.button.click_input.assert_called_once_with()

    def test_unavailable_tab_propagates_timeout_without_refresh_click(self):
        failure = TimeoutError("SAP IBP tab did not become ready")
        self.tab.wait.side_effect = failure

        with self.assertRaises(TimeoutError) as raised:
            self.refresh()

        self.assertIs(raised.exception, failure)
        self.tab.click_input.assert_not_called()
        self.button.click_input.assert_not_called()


if __name__ == "__main__":
    unittest.main()
