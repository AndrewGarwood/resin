from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
import weakref

from resin.gui import ExportOptions, Session
from resin.gui.services._export import _context_menu, _shortcut, _toolbar


class Dispatch:
    pass


class ExportSessionLifetimeTests(unittest.TestCase):
    def test_all_export_methods_hold_session_until_dialog_handling_finishes(self):
        methods = (
            (_toolbar, _toolbar.via_toolbar, "toolbar_button", {"button_id": "btn[16]"}),
            (_shortcut, _shortcut.via_keyboard_shortcut, "keyboard_shortcut", {"vkey": 43}),
            (_context_menu, _context_menu.via_context_menu, "context_menu", {"grid_id": "grid"}),
        )
        for module, export, method, invoke in methods:
            with self.subTest(method=method), TemporaryDirectory() as directory:
                session = Mock(spec=Session)
                session.connection_id = "/app/con[0]"
                session.id = "/app/con[0]/ses[1]"
                session.get_status.return_value = ""
                session.main_window.handle = 123
                references = []

                def resolve(*args):
                    dispatch = Dispatch()
                    references.append(weakref.ref(dispatch))
                    return dispatch

                session.gateway.get_session.side_effect = resolve

                def require_live_session(*args, **kwargs):
                    self.assertEqual(len(references), 1)
                    self.assertIsNotNone(references[0]())

                session.press_button.side_effect = require_live_session
                session.main_window.send_vkey.side_effect = require_live_session
                session.wait_for_component.return_value.select_context_menu_item.side_effect = (
                    require_live_session
                )
                path = Path(directory) / "export.xlsx"
                options = ExportOptions.from_dict({
                    "method": method, "invoke": invoke, "file": {"path": str(path)},
                })
                with (
                    patch.object(module, "native_save_dialog_watcher") as watcher,
                    patch.object(module, "handle_export_dialog", side_effect=require_live_session),
                    patch.object(module.fs, "wait_for_file_exists", return_value=path),
                    patch.object(module.time, "sleep"),
                    patch.object(_context_menu, "open_grid_context_menu_pywinauto"),
                    patch.object(_toolbar, "attempt_row_count", return_value=None),
                    patch.object(_shortcut, "attempt_row_count", return_value=None),
                ):
                    watcher.return_value.__enter__.return_value = Mock()
                    result = export(session, options, None)
                    self.assertTrue(result.success, str(result.error))
                self.assertIsNone(references[0]())
                session.gateway.get_session.assert_called_once_with(
                    session.connection_id, session.id,
                )

    def test_export_releases_session_when_invocation_fails(self):
        session = Mock(spec=Session)
        session.connection_id = "/app/con[0]"
        session.id = "/app/con[0]/ses[1]"
        references = []

        def resolve(*args):
            dispatch = Dispatch()
            references.append(weakref.ref(dispatch))
            return dispatch

        session.gateway.get_session.side_effect = resolve
        session.press_button.side_effect = RuntimeError("export invocation failed")
        options = ExportOptions.from_dict({
            "method": "toolbar_button", "invoke": {"button_id": "btn[16]"},
        })
        with (
            patch.object(_toolbar, "native_save_dialog_watcher"),
            patch.object(_toolbar.time, "sleep"),
        ):
            result = _toolbar.via_toolbar(session, options, None)
        self.assertFalse(result.success)
        self.assertIsNone(references[0]())


if __name__ == "__main__":
    unittest.main()
