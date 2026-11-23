# Transactions and exports

The selection/execution service is `resin.gui.Transaction`; export functions
are available through `resin.gui.ExportService`. See [GUI](gui.md) for session
provisioning and pooling, [utilities](utilities.md) for field providers, and
[SAP save dialogs](sapgui-save-dialogs.md) for the live LX02 investigation.

## Configuration

```python
from resin.gui import Transaction, TransactionOptions

transaction = Transaction(TransactionOptions.from_dict({
    "id": "TEST_LX02",
    "code": "LX02",
    "fields": {
        "wnd[0]/usr/ctxtS1_LGNUM": "warehouse_number",
        "wnd[0]/usr/ctxtS1_LGTYP-LOW": "storage_type",
        "wnd[0]/usr/ctxtWERKS-LOW": "plant_id",
    },
    "export": {
        "method": "toolbar_button",
        "invoke": {"button_id": "wnd[0]/tbar[1]/btn[16]"},
        "file": {
            "parent": "~\\path\\to\\dir\\",
            "name": "TEST_LX02.xlsx",
        },
        "overwrite": True,
    },
}))
```

`code` is required. Optional keys are `id`, `method` (execution, not export),
`fields`, `variant`, `layout`, `screens`, and `export`. Transaction construction
copies field and screen definitions; dynamic values resolve when loading each
screen, not when parsing configuration.

`Transaction(options, _id=None, *, extract_id_from_path=default_id_extractor,
strict=True, execute_fn=None, copy_to_clipboard=default_copy_to_clipboard)`:

- ID precedence: explicit `_id`, configured `id`, export filename, layout
  name, transaction code. The default filename extractor removes a leading
  `YYYY-MM-DD_` or `YYYY.MM.DD_`.
- `strict=True` rejects selection preparation without fields, a variant, or
  populated extra screens. It is a guard, not proof that the query is narrow.
- `execute_fn(transaction, session)` replaces standard/background execution.
- `set_field(id, definition)` copies an override into the transaction's working
  fields, without evaluating it.
- A selection layout (`layout: {"name": "...", "field_id": "..."}`) is inserted
  into working fields unless that field is already configured.
- A variant uses `{"name": "...", "created_by": "..."}`. Fields apply after
  variant loading and can replace variant selections.

For multi-screen transactions, `screens` entries contain a required `step_in`,
optional `step_out`, and `fields`. A step is `{"vkey": 0}` or
`{"button": "wnd[1]/tbar[0]/btn[0]"}`, never both; `vkey=0` is valid.

## Lifecycle

The usual call sequence (inside the session's COM apartment) is:

1. `open(session)`: start the transaction.
2. `populate_selection_screen(session)`: load variant, initial fields, then
   additional screens.
3. `execute(session)`: run the selected execution method.
4. `handle_post_execute(session)`: optionally select an export layout.
5. `export(session)`: save data, or complete without a file.
6. `get_result()`: build a `pyqi.Result[TransactionDetails]`.

`SessionPool` invokes these stages on its workers. For manual automation,
explicitly wait for SAP to become idle between operations that initiate server
work; `Transaction` is not a general-purpose SAP completion detector.

Stages progress from `CREATED` through `OPENING`, `POPULATING_SELECTION`,
`READY_TO_EXECUTE`, `DISPATCHING_EXECUTE`, `EXECUTION_RUNNING`, `POST_EXECUTE`,
`READY_TO_EXPORT`, optional `EXPORTING`, and `COMPLETED`. Failures can transition
to `FAILED`. `wait_for_stage(target, *, timeout=seconds)`, `stage_history`,
`failure`, and `is_terminal` observe local synchronized state without COM calls.
Opening again is allowed from `COMPLETED`; use a new transaction after failure.

The standard execution method sends F8, then may acknowledge a distinct active
window with Enter. The `async` method configures immediate background execution;
it does not create a Python coroutine or poll a background job to completion.
Provide a custom execution callback when a transaction has different semantics.

### Field application

All operations for one screen are prepared before that screen's first configured
field write. A preparation failure therefore performs no configured writes on
that screen. SAP navigation, variant loading, previous screens, and earlier COM
writes are not rolled back.

- `txt`/`ctxt`: string, number, boolean, or `None` (clear).
- `chk`: boolean only.
- `rad`: a fully specified radio field and `RADIO_BUTTON_SELECT`.
- Lists/tuples or include/exclude options: standard SAPLALDB multiple selection.

Multi-selection replaces all four include/exclude value/range categories.
Single values use clipboard paste (Shift+F12) by default; pass
`copy_to_clipboard=None` for row-by-row entry. Ranges use table cells.
Row entry commits full pages, scrolls, checks the actual visible position, and
raises if SAP cannot expose a requested row. Custom selection dialogs are not
supported. Dialog failures leave the screen open for inspection, without rollback.

## Export configuration

`ExportOptions` contains `method`, `invoke`, `file`, `save`, optional `layout`,
and `overwrite` (default `False`).

| Method | Required invocation | Implementation |
| --- | --- | --- |
| `none` | None | No file export requested |
| `toolbar_button` | `invoke.button_id` | Press a scripted toolbar button |
| `keyboard_shortcut` | `invoke.vkey` | Check and send a permitted SAP virtual key |
| `context_menu` | `invoke.grid_id` | Open grid context menu with Windows automation, select item |

Call the registered functions with **three arguments**, for example
`ExportService.via_toolbar(session, options, None)`. The third argument is a
`NativeSaveDialogOptions`, a zero-argument factory returning one, or `None` for
defaults; it is not an optional positional argument in these function signatures.
The registry dispatch is `EXPORT_METHOD_REGISTRY.call(method, session, options,
native_options)`.

For context-menu export, `menu_item_id` defaults to `&XXL`. This implementation
right-clicks the grid using coordinates and Windows automation, then selects
the item through COM and confirms an intermediate SAP dialog. It is not an
equivalent replacement for LX02's toolbar export in every transaction/layout.

An export layout is separate from a selection-screen layout. Its selector
contains `name`, `grid_id`, either `btn_id` or `vkey`, and optional
`iter_reverse`. `handle_post_execute` opens the chooser and selects a row by
layout name.

### File paths

`FileOptions` accepts `path`, or `outdir` plus `name` (default `export.xlsx`).
`~` expansion is handled by `pyqi.fs.to_path`. `path`, `dir`, and `name` are
mutable properties. Date codes are **not** expanded by `from_dict`.

For a configured name such as `%Y-%m-%d_TEST_LX02.xlsx`, explicitly format it:

```python
transaction.options.set_export_path(ref_date="today")
```

`FileOptions.formatted_path` returns a formatted path without updating the
stored one. `set_export_path` updates the transaction's export file. Formatting
can also apply Python `.format(*args, **kwargs)` placeholders.

### Save-dialog handling

Export methods retain the raw exporting `GuiSession` dispatch for the entire
invocation/dialog scope, so SAP's scriptable replacement can remain active.
They start a native-dialog watcher *before* the invocation. A native
modal dialog can block the initiating COM call, so a watcher on another COM
thread must be ready to handle it.

The SAP save dialog defaults to:

- Directory: `wnd[1]/usr/ctxtDY_PATH`
- Filename: `wnd[1]/usr/ctxtDY_FILENAME`
- Confirm: `wnd[1]/tbar[0]/btn[0]`

Override these with `export.save` for another SAP dialog. These IDs cannot
address a Windows-native Save As dialog. `handle_export_dialog` initially
waits up to five seconds for the native watcher, then looks for the SAP directory
field, then waits for the native watcher for the remaining timeout.

The native watcher defaults to a 300-second timeout and 0.25-second poll.
It waits up to five seconds for enabled, visible filename edits after detecting
the dialog, because the top-level window can appear before its controls.
It requires a visible, enabled, matching dialog owned by the SAP main-window
handle, claims that handle, fills the selected Edit with a full path, and
confirms Save. Its default selector chooses the widest available Edit control.
Customize `NativeSaveDialogOptions` for localization or different controls.
The export UI lock serializes exports within this Python process, not across
independent Python processes.

## Results and operational limits

Exports return `Result[ExportDetails]` with path and optional grid row count.
`TransactionDetails` includes transaction ID/code, execution telemetry,
`CompletedExport` (path, row count, export telemetry), and last cached SAP
status. Always inspect `result.success` and `result.error`; `COMPLETED` alone
does not establish export success.

`build_result_dict(results, key_normalizer=None)` indexes by transaction ID
and requires populated result data. Normalized key collisions overwrite earlier
entries; choose unique keys.

Current implementation limits to account for:

- `overwrite` is parsed but does not choose the SAP Replace button or disable
  native overwrite confirmation. Use a new filename for unattended tests.
- File-existence waiting does not prove the file was newly written, complete,
  or a valid workbook. Use unique names and independently validate output.
- The SAP save path does not create the output directory; create it beforehand.
- **`Transaction.export()` attempts to terminate a process holding the output
  file, matching by filename.** This can affect an Excel process with other open
  workbooks. Do not use that convenience path in a shared environment unless
  process ownership is understood. The live probe calls the export service
  directly and does not terminate Excel.
- Native overwrite handling searches desktop dialogs without the initial
  save watcher's owner filter. Avoid concurrent interactive Save As operations.
- A native watcher timeout is not a hard deadline for a blocked COM call.
  Pool future timeouts do not cancel a COM operation already in progress.
