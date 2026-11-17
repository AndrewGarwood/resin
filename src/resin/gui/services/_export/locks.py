"""
*`@file`* `gui/services/_export/locks`
"""
from pyqi import LockManager


NATIVE_DIALOG_HANDLE_LM = LockManager(name="NativeDialogLockManager")

EXPORT_UI_LM = LockManager(name="SapGuiExportLockManager")


__all__ = ["NATIVE_DIALOG_HANDLE_LM", "EXPORT_UI_LM"]