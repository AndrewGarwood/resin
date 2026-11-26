# SAP GUI versus native Windows save dialogs

## Finding and fix

For the tested LX02 export, **retain a raw `GuiSession` COM dispatch until
export invocation and dialog handling have finished**. Retaining only the
`GuiApplication` scripting-engine dispatch was not sufficient.

Resin normally keeps stable IDs and re-resolves COM objects on each operation.
That remains the general model. However, the short-lived resolutions alone
were insufficient for SAP's save-dialog substitution in this experiment.
All three export services now use a shared, scoped session-reference lease:

1. Acquire the process-local export UI lock.
2. Resolve and hold the exporting session's raw dispatch on the calling thread.
3. Start the native watcher, invoke export, and handle the resulting dialog.
4. Stop the watcher and release the raw session reference, including on failure.

No dispatch is cached globally or shared with the watcher thread. No SAP
registry setting, recording mode, test-tool mode, or security setting is changed.
The native watcher remains available when SAP still presents a native dialog.

## SAP configuration

In SAP GUI Options, navigate to **Accessibility & Scripting > Scripting** and
leave **Show Native Microsoft Windows Dialog** unchecked when you want SAP's
scriptable replacements. SAP's installed documentation explains that native
Save As/Open dialogs cannot be accessed through SAP GUI scripting; their
replacement can be disabled by that checkbox.

The observed per-user setting was already:

```text
HKCU\Software\SAP\SAPGUI Front\SAP Frontend Server\Scripting
    ShowNativeWinDlgs = 0
```

That registry value alone did not predict the dialog used. It is evidence of
the persisted preference, not a getter for a running client's effective state.
Prefer changing options through SAP GUI rather than editing registry keys.
Follow SAP's instructions about applying/restarting the client if you change
the preference; this investigation did not change it.

Do not use `session.Record=True` just to influence dialogs: recording mode
changes other UI behavior. `TestToolMode` also changes popup handling and
server update behavior; it is not a native-save-dialog preference.
`IsActive` describes the active session window, not whether scripting is active.

## Live evidence (2026-11-23)

Environment:

- Configured connection from `tests.config.json`, one provisioned source
  session; each probe created and subsequently closed its own extra session.
- LX02 selection: warehouse `USN`, storage type `PCR`, plant `U633`.
- Export invocation: `wnd[0]/tbar[1]/btn[16]`.
- Installed scripting API reported `MajorVersion=7700`, `MinorVersion=257`,
  `Revision=1`, `Patchlevel=8`.
- `ShowNativeWinDlgs=0`, `Record=False`, `TestToolMode=0`;
  server scripting enabled, read-only and recording-disabled flags both false.

| Session-reference policy | Outcome |
| --- | --- |
| Original Resin resolution; no retained session | Native Save As; valid export, 28.203 seconds |
| Hold application only, original resolution | Native Save As; watcher readiness failure, manually cancelled |
| Hold raw session, original resolution | SAP dialog in 2/2 runs; valid exports |
| Updated Resin, no extra manually held dispatch | SAP dialog in 3/3 runs; valid exports, 13.859-14.110 seconds |
| Diagnostic legacy-resolution switch after readiness fix | Native dialog in 2/2 runs; automatic saves, 27.297-27.703 seconds |

Successful exports were checked as non-empty XLSX ZIP archives, with intact ZIP
members, a workbook part, worksheets, and **793 populated worksheet rows**.
The number includes report headings; it is not a claim of 793 inventory records.
Filenames were unique, so stale files could not satisfy the verification.

This controlled comparison verifies the LX02 toolbar path on this installed
client. It does not prove every SAP transaction, frontend version, or export
format uses the same dialog rules. Context-menu and keyboard-shortcut methods
share the lifetime fix and are covered by mocked lifetime tests, not separate
live transaction certifications.

## Why the native run hung past 300 seconds

The native Save As dialog can block the initiating COM `Press()` call. The
watcher is started first on another thread specifically to handle that modal
dialog while the exporting thread is blocked.

In the failed run, the watcher saw the native dialog but initially found no
enabled, visible Edit control. Its diagnostic dump immediately afterward
showed the filename Edit visible and enabled. This exposed a startup race:
the dialog can become eligible before its filename control is ready.

The watcher now waits up to **five seconds**, with 0.1-second polling and
cancellation checks, for that control. Absence after the deadline still raises
an explicit failure. Two focused tests cover delayed availability and expiry;
the two later native exports completed without manual interaction.

A watcher failure alone cannot interrupt a COM call. `handle_export_dialog`
cannot inspect that failure until invocation returns. Likewise,
`SessionPoolOptions.export_timeout=300` limits coordinator future waiting;
it is **not a COM cancellation mechanism**. Shutdown may also wait for a worker
still blocked in SAP. The original probe called the export service directly,
not `SessionPool.run`, so pool timeout settings did not apply to that probe.

The live probe now has additional recovery, confined to the test:

- On a native-handler error, cancel the exact test-session-owned Save As dialog,
  then preserve/raise the original error.
- At its default 60-second export-dialog deadline, cancel matching native
  Save As dialogs only if their owner chain leads to the test SAP window.
- Never terminate SAP or Excel processes.

This is not a universal hard process deadline: server calls, unknown SAP
modals, or a hung desktop API can still block. For strict unattended deadlines,
use process isolation plus a supervisor and explicit ownership-aware recovery.
Do not assume stopping Python will close a SAP-owned modal dialog.

## Running the probe

From the Resin package root:

```powershell
# Verify the normal library path uses SAP's scriptable dialog.
.\.venv\Scripts\python.exe .\tests\sapgui_export_probe.py --repeat 3 --expect-dialog sapgui

# Controlled negative comparison; diagnostic-only bypass of the lifetime fix.
.\.venv\Scripts\python.exe .\tests\sapgui_export_probe.py --legacy-resolution --expect-dialog native

# Extra explicit session retention for the original-lifetime comparison.
.\.venv\Scripts\python.exe .\tests\sapgui_export_probe.py --legacy-resolution --hold session --expect-dialog sapgui
```

Options: `--hold none|application|session`, `--repeat 1..10`,
`--expect-dialog either|sapgui|native`, `--dialog-timeout SECONDS` (default 60,
positive and at most 300), and `--config PATH`.

The probe reads provisioner and `test-lx02` options from `tests.config.json`,
requires one source session and LX02 toolbar export.

Names include a timestamp, mode, run index, and random suffix. JSON records on
stdout identify the environment, actual handled dialog, path, time, byte count,
SHA-256, and worksheet row counts. Errors produce a nonzero exit.

It uses the normal transaction preparation/execution lifecycle, but invokes
`via_toolbar(session, options, None)` directly to avoid
`Transaction.export()`'s process-termination side effect. Existing SAP source
sessions/connections are not closed. Automatically opened Excel workbooks are
left alone; close only the test workbooks manually if necessary.

## Sources and validation

The installed SAP help used for the product/API facts:

- [Scripting options](<C:\Program Files (x86)\SAP\FrontEnd\SAPgui\SAPguihelp\EndUserHelp\EN\7ddb7c9c4a4c43219a65eee4ca8db001.html>)
- [GuiSession API](<C:\Program Files (x86)\SAP\FrontEnd\SAPgui\SAPguihelp\ScriptingAPI\a4e022f6c155414d9c8ae8eba422cac5.html>)
- [GuiApplication API](<C:\Program Files (x86)\SAP\FrontEnd\SAPgui\SAPguihelp\ScriptingAPI\a020c8f8cfaf48ec9b579d5961889639.html>)
- [SAP Note 1974590](https://me.sap.com/notes/1974590), referenced by installed
  help; note content was not inspected and may require SAP access.

Ten new regression tests pass: raw-session lifetime for all three export
methods and exception release; native control readiness/expiry; session
creation/capacity polling; and meaningful XLSX output verification.
The full suite ran 83 tests with 18 failures and 7 errors. An untouched HEAD
snapshot ran the original 73 tests with the same 18 failures and 7 errors,
confirming those field-resolution, multi-selection, and IBP watcher problems
pre-date this change. They were not modified as part of this investigation.
The required session-creation path also exposed and fixed `Connection` importing
polling helpers from the obsolete COM runtime shim instead of the shared runtime.
See [transactions](transactions.md) for remaining export limitations.
