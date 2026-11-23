from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import Mock, patch

from resin.gui.services._export.types import NativeSaveDialogOptions
from resin.gui.services._export.watcher import NativeSaveDialogWatcher


class NativeSaveReadinessTests(unittest.TestCase):
    def setUp(self):
        self.watcher = NativeSaveDialogWatcher(
            cancel=Event(), done=Event(), handled_event=Event(),
            thread=None, backend="win32",
        )
        self.options = NativeSaveDialogOptions(
            backend="win32", save_edit_selector=lambda edits: next(iter(edits)),
        )

    def test_waits_for_filename_edit_after_dialog_becomes_visible(self):
        dialog = Mock()
        edit = Mock()
        button = Mock()
        dialog.descendants.side_effect = [[], [edit], [button]]
        module = "resin.gui.services._export.watcher"
        with (
            TemporaryDirectory() as directory,
            patch(f"{module}.winauto.control_is_available", return_value=True),
            patch(f"{module}.handle_save_edit") as save_edit,
            patch(f"{module}.handle_overwrite"),
            patch(f"{module}.time.sleep"),
            patch.object(self.watcher.cancel, "wait") as wait,
        ):
            outpath = Path(directory) / "export.xlsx"
            self.watcher.handle_dialog(dialog, self.options, outpath)
            wait.assert_called_once_with(0.1)
            save_edit.assert_called_once_with(edit, str(outpath), self.options.retry)
            button.click_input.assert_called_once()
            self.assertTrue(self.watcher.handled_event.is_set())

    def test_missing_edit_still_fails_after_readiness_deadline(self):
        dialog = Mock()
        dialog.descendants.return_value = []
        module = "resin.gui.services._export.watcher"
        with (
            TemporaryDirectory() as directory,
            patch(f"{module}.time.monotonic", side_effect=[0.0, 5.0]),
            patch(f"{module}.inspect_descendants"),
            patch(f"{module}.handle_save_edit") as save_edit,
        ):
            with self.assertRaisesRegex(RuntimeError, "Failed to handle save dialog"):
                self.watcher.handle_dialog(
                    dialog, self.options, Path(directory) / "export.xlsx",
                )
            save_edit.assert_not_called()
            self.assertFalse(self.watcher.handled_event.is_set())


if __name__ == "__main__":
    unittest.main()
