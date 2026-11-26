"""Opt-in live LX02 export probe; never runs during unittest discovery."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import threading
import time
from unittest.mock import patch
from uuid import uuid4
from xml.etree import ElementTree
from zipfile import ZipFile

from resin.gui import (
    SessionProvisioner,
    SessionProvisionerOptions,
    Transaction,
    TransactionOptions,
    default_sap_gui_launcher,
)
from resin.gui.services._export import _toolbar, dialog, via_toolbar
from resin.gui.services._export.watcher import NativeSaveDialogWatcher
from resin.gui.utils.concurrency import wait_for_session_idle
from resin.utils.runtime import com_apartment
import winreg
import win32con
import win32gui
from resin.utils.winauto import is_owned_by


SCRIPTING_KEY = r"Software\SAP\SAPGUI Front\SAP Frontend Server\Scripting"
OUTPUT_DIRECTORY = Path.home() / "workspaces.local\\resin\\test_data"


def native_dialog_setting() -> int | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, SCRIPTING_KEY) as key:
            value, _ = winreg.QueryValueEx(key, "ShowNativeWinDlgs")
    except FileNotFoundError:
        return None
    if not isinstance(value, int):
        raise TypeError("ShowNativeWinDlgs is not an integer registry value")
    return value


def workbook_evidence(path: Path) -> dict[str, object]:
    if path.stat().st_size == 0:
        raise RuntimeError(f"Export is empty: {path}")
    with ZipFile(path) as workbook:
        corrupt_member = workbook.testzip()
        if corrupt_member is not None:
            raise RuntimeError(f"Corrupt XLSX member: {corrupt_member}")
        workbook.getinfo("xl/workbook.xml")
        sheet_names = [
            name for name in workbook.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        ]
        if not sheet_names:
            raise RuntimeError("Export has no worksheets")
        row_counts = []
        populated_row_counts = []
        namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        for name in sheet_names:
            root = ElementTree.fromstring(workbook.read(name))
            rows = root.findall(f".//{namespace}row")
            row_counts.append(len(rows))
            populated_row_counts.append(sum(
                any(element.text for element in row.iter()
                    if element.tag in (f"{namespace}v", f"{namespace}t"))
                for row in rows
            ))
        if not any(count > 1 for count in populated_row_counts):
            raise RuntimeError("LX02 export has no data rows")
    return {
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "worksheet_rows": row_counts,
        "populated_worksheet_rows": populated_row_counts,
    }


def cancel_native_dialog(handle: int, owner: int) -> bool:
    if (
        win32gui.IsWindow(handle)
        and win32gui.GetClassName(handle) == "#32770"
        and win32gui.GetWindowText(handle) == "Save As"
        and is_owned_by(handle, owner)
    ):
        win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)
        print(json.dumps({"event": "cancel_native_dialog", "handle": handle}), flush=True)
        return True
    return False


def probe(
    hold: str, repeat: int, expect_dialog: str,
    config_path: Path, dialog_timeout: float, legacy_resolution: bool,
) -> None:
    with config_path.open(encoding="utf-8") as source:
        config = json.load(source)["gui"]
    provisioner_options = SessionProvisionerOptions.from_dict(config["provisioner"])
    if provisioner_options.session_count != 1:
        raise ValueError("This probe requires provisioner session_count=1")
    definition = config["transactions"]["test-lx02"]
    if definition["code"] != "LX02":
        raise ValueError("This probe only executes the read-only LX02 transaction")
    if definition["export"]["method"] != "toolbar_button":
        raise ValueError("This probe requires the LX02 toolbar export method")

    with com_apartment():
        provisioned = SessionProvisioner(
            provisioner_options, launcher=default_sap_gui_launcher
        ).provision()
        source_session = provisioned.bindings[0].locator.resolve()
        connection = source_session.connection
        session = connection.create_session(
            source_session=source_session,
            timeout=provisioner_options.create_timeout,
            poll_interval=provisioner_options.create_poll_interval,
        )
        held_dispatch = None
        try:
            if hold == "application":
                held_dispatch = session.gateway.get_application()
            elif hold == "session":
                held_dispatch = session.gateway.get_session(connection.id, session.id)
            raw = session.gateway.get_session(connection.id, session.id)
            print(json.dumps({
                "event": "environment",
                "session": session.id,
                "hold": hold,
                "scripting_reference_retained": held_dispatch is not None,
                "library_session_retention": not legacy_resolution,
                "ShowNativeWinDlgs": native_dialog_setting(),
                "record": raw.Record,
                "test_tool_mode": raw.TestToolMode,
                "read_only": raw.Info.ScriptingModeReadOnly,
                "recording_disabled": raw.Info.ScriptingModeRecordingDisabled,
            }), flush=True)
            del raw
            for run in range(1, repeat + 1):
                data = deepcopy(definition)
                export = data["export"]
                export["overwrite"] = True
                export["file"] = {
                    "outdir": str(OUTPUT_DIRECTORY),
                    "name": (
                        f"{datetime.now():%Y-%m-%d_%H%M%S}_TEST_LX02_"
                        f"{hold}_{run}_{uuid4().hex[:8]}.xlsx"
                    ),
                }
                transaction = Transaction(TransactionOptions.from_dict(data))
                options = transaction.export_options
                if options is None:
                    raise RuntimeError("LX02 export options are missing")
                options.file.dir.mkdir(parents=True, exist_ok=True)
                if options.file.path.exists():
                    raise FileExistsError(options.file.path)
                observed: list[str] = []
                observed_lock = threading.Lock()
                owner = session.main_window.handle
                original_sap = dialog._try_sapgui_dialog
                original_native = NativeSaveDialogWatcher.handle_dialog

                def trace_sap(*args, **kwargs):
                    handled = original_sap(*args, **kwargs)
                    if handled:
                        with observed_lock:
                            observed.append("sapgui")
                    return handled

                def trace_native(*args, **kwargs):
                    try:
                        result = original_native(*args, **kwargs)
                    except Exception:
                        cancel_native_dialog(int(args[1].handle), owner)
                        raise
                    with observed_lock:
                        observed.append("native")
                    return result

                transaction.open(session)
                wait_for_session_idle(session)
                transaction.populate_selection_screen(session)
                transaction.execute(session)
                wait_for_session_idle(session)
                transaction.handle_post_execute(session)
                started = time.monotonic()
                expired = threading.Event()

                def expire_native_dialog():
                    expired.set()
                    print(json.dumps({
                        "event": "dialog_deadline", "seconds": dialog_timeout,
                    }), flush=True)
                    win32gui.EnumWindows(
                        lambda handle, _: cancel_native_dialog(handle, owner) or True,
                        None,
                    )

                timer = threading.Timer(dialog_timeout, expire_native_dialog)
                timer.start()
                try:
                    with (
                        patch.object(dialog, "_try_sapgui_dialog", trace_sap),
                        patch.object(NativeSaveDialogWatcher, "handle_dialog", trace_native),
                        patch.object(
                            _toolbar, "_retain_scripting_session",
                            lambda _session: nullcontext(),
                        ) if legacy_resolution else nullcontext(),
                    ):
                        # Transaction.export also kills a process holding the file.
                        # The probe intentionally leaves unrelated Excel processes alone.
                        result = via_toolbar(session, options, None)
                finally:
                    timer.cancel()
                    timer.join()
                if expired.is_set():
                    raise TimeoutError("Live probe exceeded its native-dialog deadline")
                if not result.success:
                    error = result.error
                    message = f"LX02 export failed: {result.message}; error={error!r}"
                    if isinstance(error, BaseException):
                        raise RuntimeError(message) from error
                    raise RuntimeError(message)
                if len(observed) != 1:
                    raise RuntimeError(f"Expected one handled dialog, observed {observed!r}")
                evidence = workbook_evidence(options.file.path)
                print(json.dumps({
                    "event": "export",
                    "hold": hold,
                    "run": run,
                    "dialog": observed[0],
                    "seconds": round(time.monotonic() - started, 3),
                    "path": str(options.file.path),
                    **evidence,
                }), flush=True)
                if expect_dialog != "either" and observed[0] != expect_dialog:
                    raise AssertionError(
                        f"Expected {expect_dialog} dialog, observed {observed[0]}"
                    )
        finally:
            held_dispatch = None
            connection.close_session(session)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hold", choices=("none", "application", "session"), default="none")
    parser.add_argument("--repeat", type=int, choices=range(1, 11), default=1)
    parser.add_argument("--expect-dialog", choices=("either", "sapgui", "native"), default="either")
    parser.add_argument("--dialog-timeout", type=float, default=60.0)
    parser.add_argument(
        "--legacy-resolution", action="store_true",
        help="Diagnostic only: disable library session retention for the A/B comparison",
    )
    parser.add_argument(
        "--config", type=Path,
        default=Path(__file__).resolve().parents[1] / "tests.config.json",
    )
    args = parser.parse_args()
    if not 0 < args.dialog_timeout <= 300:
        parser.error("--dialog-timeout must be greater than zero and at most 300 seconds")
    probe(
        args.hold, args.repeat, args.expect_dialog, args.config,
        args.dialog_timeout, args.legacy_resolution,
    )


if __name__ == "__main__":
    main()
