# resin

## AO and IBP workbook controllers

The controllers live in `resin.ao` and `resin.ibp`. They share single-use,
single-threaded Excel ownership, staged workbook transactions, cooperative
deadlines, cooldown decisions, explicit outcomes, and recovery-aware publication.
They use `noxl` for Excel sessions, `lute` for logging, and resin's existing
`pyqi`-based field resolution and Windows automation helpers.

**Validation status:** covered by fake COM/session/UI and filesystem tests only.
No live Excel, AO, IBP, login, or production-workbook validation has been
performed. Legacy `shared.sap` controllers and report imports have intentionally
not been redirected to these controllers; migrate explicitly after validating
disposable workbook copies in your SAP environment.

### Analysis for Office

```python
from resin import ao, RefreshStatus

options = ao.ControllerOptions.from_dict({
    "staging": r"C:\Temp\resin",
    "refresh_cooldown_minutes": 30,
    "staging_policy": "always",
})
workbook = ao.WorkbookOptions.from_dict({
    "filepath": r"C:\Data\analysis.xlsm",
    "template": r"C:\Data\analysis.template.xlsx",
    "ds_alias": "DS_1",
    "prompts": {"P_DATE": {"sentinel": "FIRST_DAY_OF_MONTH"}},
    "set_prompts": True,
})

with ao.Controller(options) as controller:
    outcome = controller.refresh(workbook)
    if outcome.status == RefreshStatus.REFRESHED:
        print(outcome.refreshed_at, outcome.publication)
```

Definitions are copied without evaluating dynamic prompts at options creation.
`refresh` resolves enabled prompts exactly once per operation through
`resin.models._field.resolve_field_dict`, before prompt writes; retries reuse the
resolved values. A later refresh resolves the definitions again. Pass
`resolve_prompts=False` if the caller has already resolved them or a literal
string must not be interpreted as a sentinel. GUI action sentinels and unsupported
prompt shapes are not workbook prompt commands.

The new `refresh` API honors `WorkbookOptions.set_prompts` when its override is
omitted. `refresh_workbook(workbook, set_prompts=False, timeout_minutes=30,
force=False, *, resolve_prompts=True)` retains the old explicit flag default and
returns `None`. It accepts a second positional prompt flag. Prefer `refresh` for
distinguishing a refresh from a cooldown skip.

AO checks the exact configured add-in (`SapExcelAddIn` by default), datasource
readiness and SAP command responses. It retains the initial refresh, pause,
prompts, resume, final refresh sequence, with consistent pause flags:
`INACTIVE` uses refresh `Off` / variable submission pause `On`; `ACTIVE` uses
`On` / `Off`. This corrects the inverted legacy enum mapping. Restoration
failure invalidates the controller rather than allowing another operation with
uncertain add-in state.

Completion conservatively requires an advancing workbook refresh timestamp and
Excel readiness. This predicate and the corrected pause sequence still require
installed-version verification; unchanged timestamps time out instead of
returning a fabricated completion time. Details explicitly distinguish offline
completion checks from live validation.

### IBP

```python
from resin import ibp

options = ibp.ControllerOptions.from_dict({
    "staging": r"C:\Temp\resin",
    "refresh_cooldown_minutes": 30,
    "connection": {"name": "My IBP Connection"},
    "connection_mode": "workbook",
})
workbook = ibp.WorkbookOptions.from_dict({
    "path": r"C:\Data\planning.xlsm",
    "sheetname": "Demand View",
    "data_origin": "A5",
    "search_headers": ["Material"],
})

with ibp.Controller(options) as controller:
    outcome = controller.refresh(workbook, method=ibp.RefreshMethod.PYWINAUTO)
```

Workbook mode is the default. Without a binding verifier it conservatively calls
`Connect` for each non-skipped target, requires an explicit successful boolean/
integer return (`True`/`1`), and checks the connection name. This is **not** a
claim that the installed add-in actually returns that shape. Supply a
deployment-verified binding adapter if your add-in differs. Configuring a
planning area, server URL, or connection ID requires such a verifier; matching
workbook metadata alone cannot verify them.

During `Connect`, a background pywinauto watcher acknowledges the optional
outdated-add-in warning using its OK button. It matches the warning title and
version-message text only within the owned Excel process; other warnings are
left untouched. The watcher stops when `Connect` returns, including on failure,
and does not require the warning to appear. Watcher failures are logged and
raised after `Connect` returns; they cannot interrupt a blocked COM call.
This dialog handling has fake-window test coverage, not live SAP validation.

The controller rejects nonempty filters and `refresh_only=False`: it does not
silently apply filters or perform writeback. API refresh remains an explicit
choice and may be disabled by your IBP administrator. There is no automatic
API/UI fallback and no replay after an ambiguous refresh error.

Both backends wait for a stable, advanced `SOP_Refresh_Timestamp`; the API's
invocation time is not a completion timestamp. IBP defined-name properties can
be range-backed or scalar constants: for scalar names, Excel error 1004 from
`RefersToRange` selects `Name.Value` instead. A blank timestamp value is treated
as unavailable; a missing name, malformed timestamp, or other COM failure now
raises explicitly instead of being hidden as `None` throughout completion
polling. Debug logs distinguish the return from `click_input`, the return from
refresh dispatch, and observation of an advanced timestamp. An unchanged
timestamp still waits only until the operation deadline (30 minutes by default;
set `refresh(..., timeout_minutes=...)` for a shorter diagnostic run).
UI refresh explicitly uses
pywinauto's `uia` backend, attaches to the owned Excel PID, and finds the
`SAP IBP` `TabItem` within the target workbook window before clicking its
visible `Refresh` button. Both searches stay within that workbook, and readiness
waits use the remaining operation deadline. An optional `workbook_handle`
selects the exact window; otherwise the escaped workbook name is used.
The default `win32` backend sees native Ribbon containers, not the accessible
tab items, so a Win32 descendant dump can omit a visibly present `SAP IBP` tab.
Inspect the workbook through `Application(backend="uia")` when diagnosing Ribbon
controls. UI refresh serializes focus/dispatch/completion and needs an exclusive interactive
Windows desktop; a locked desktop, another automation process, or user focus
changes can interfere. Opening a controller is never a headless-login promise.

#### Experimental anchor workbook

Set `connection_mode="anchor"` and pass `binding_verifier=...` to opt in.
An explicit connection name and a verifier are mandatory. The verifier signature
is:

```python
def verify_binding(
    *, workbook, worksheet, requested, connections, connect_result
) -> ibp.BindingObservation:
    ...
```

Implement this adapter against your installed add-in's documented/observed
connection results. `VALID` must prove both usable authentication and the complete
requested identity. `MISSING` and `EXPIRED` request bounded connection work before
refresh; mismatches raise `ConnectionBindingError`. Raw `GetConnections` results
remain structured. Do not mark a session valid merely because its workbook has a
matching `SOP_Connection_Name`.

In anchor mode `__enter__` creates a uniquely named local tracked `.xlsx`,
activates it, connects, and verifies the binding before returning. If blank
workbooks are unsupported, configure `anchor_seed` and `anchor_sheetname` to use
a private copy of a sanitized IBP workbook instead. The seed itself is not
modified. The anchor stays open between target refreshes, and closes before
Excel exits. Valid target bindings can reuse authentication without `Connect`;
missing target bindings still require a supported binding/Connect operation.
Entry failure is an error, not a silent fallback to workbook mode.

The anchor is **not validated for your installed IBP version**. Before adopting
it, compare two disposable target workbooks in one owned Excel process against
workbook mode. Verify connection/planning-area identity, actual completed data,
Connect counts, login-dialog counts, anchor lifetime, expiry/cancellation,
conflicting targets, and cleanup. Authentication reuse and target binding are
separate observations.

### Outcomes, staging and failures

`refresh` returns an immutable `RefreshOutcome` with `REFRESHED` or
`SKIPPED_COOLDOWN`, actual workbook timestamps, operation ID, timings, publication
disposition, and typed add-in details. A skip closes its target without saving
or publishing. `force=True` bypasses cooldown in the new API for either add-in.
Future timestamps clamp cooldown with a warning. Missing timestamps require a
refresh; malformed values raise rather than being stripped into a plausible date.
Workbook timestamps are treated as local-naive values and honor the workbook's
1900/1904 date system.

The deprecated IBP `refresh_workbook` adapter returns `RefreshInfo`, including
legacy skip placeholders. New code should inspect the explicit status rather
than treating those placeholders as real connection identities. Historical
case-sensitive module spellings are compatibility imports within resin; they
do not redirect the separate legacy package automatically.

Staging defaults to **always**, including local workbooks. Use `"never"` for an
intentional in-place save, or `"auto"` with configured `stage_roots` for local
cloud-sync roots (UNC paths are also staged). Raw HTTP(S) sources are rejected;
filesystem staging is not a download/upload transport. Each operation gets a
unique directory so repeated or same-basename workbooks cannot overwrite one
another's staging files. Staging itself must be on a local filesystem.

Publication closes Excel's target handle first, coordinates resin writers with
an exclusive sibling lock file, checks source content fingerprints, verifies a
new sibling copy, creates a uniquely named backup beside the destination, and
then uses same-directory replacement. Failures retain recovery output and report
the relevant paths in the exception's `context`. Backups are retained for the
caller to manage. No shared staging directory is swept or recursively deleted.

This is not remote compare-and-swap: arbitrary noncooperating editors can race
the final check, and network/cloud providers may not supply local filesystem
atomicity or synchronization guarantees. Ensure exclusive access when those
guarantees matter. A stale `.resin-publish.lock` causes a bounded wait/failure;
remove one only after verifying its owner is gone. In-place saving offers no
original-file rollback on save failure.

Controllers own one isolated Excel process, are single-use, and reject reentry,
concurrent/reentrant refreshes and cross-thread access. Borrowed sessions are
explicitly rejected because the underlying save watchdog can terminate its
session's Excel process. Only an owned process is eligible for that watchdog.
Fatal COM/save failures require a new controller.

One monotonic refresh budget covers controllable waits through publication;
startup has a separate budget. These are **cooperative deadlines**, not a way
to interrupt arbitrary blocked COM calls. The underlying save watchdog is the
exception. Cancellation/failure closes targets without another implicit save,
releases the add-in/anchor, and unwinds the owned Excel session.

Run the mock-only controller suite without starting Excel or SAP:

```powershell
python -m unittest discover -s tests -p test_workbook_core.py
python -m unittest discover -s tests -p "*controller.py"
python -m unittest discover -s tests -p test_ibp_refresh_ui.py
python -m unittest discover -s tests -p test_ibp_completion.py
```

## Transaction field definitions

Transaction fields are unresolved configuration definitions. Construction and
`Transaction.set_field()` copy definitions without evaluating them. Immediately
before loading each screen, resin resolves and validates all of that screen's
fields, then applies the prepared operations in configuration order. Reopening
and populating a transaction evaluates its definitions again.

```json
{
  "code": "EXAMPLE",
  "fields": {
    "wnd[0]/usr/ctxtS_DATE-LOW": {
      "sentinel": "FIRST_DAY_OF_MONTH",
      "anchor": {"sentinel": "CURRENT_DAY"}
    },
    "wnd[0]/usr/chkP_DETAIL": true,
    "wnd[0]/usr/radP_SUMMARY": "RADIO_BUTTON_SELECT"
  }
}
```

Built-in date providers are registered automatically. Bare sentinel strings are
supported as field values and individual selection values/range bounds. Use
explicit sentinel objects for nested provider arguments; ordinary strings inside
arguments and dictionaries remain literal. Providers receive a resolved `args`
list plus non-reserved object keys as keyword arguments. Provider results are
not evaluated a second time.

Text fields (`txt`, `ctxt`) accept JSON scalars; `null` clears the field.
Checkboxes (`chk`) require booleans. Radio selections require a field ID that
includes the radio option and accept either `"RADIO_BUTTON_SELECT"` or
`{"sentinel": "RADIO_BUTTON_SELECT"}` without extra keys.

### Multiple selection

A list or tuple is shorthand for include selections: elements with exactly
`lower` and `upper` keys become `include.ranges`; all other elements become
`include.values`. Order is preserved within each group. For example:

```json
{
  "fields": {
    "wnd[0]/usr/ctxtS_PLANT-LOW": [
      "1000",
      "1100",
      {"lower": "2000", "upper": "2999"}
    ]
  }
}
```

For exclusions, use explicit options:

```json
{
  "include": {
    "values": ["1000"],
    "ranges": [{"lower": "2000", "upper": "2999"}]
  },
  "exclude": {
    "values": ["2100"],
    "ranges": [{"lower": "2200", "upper": "2299"}]
  }
}
```

The options object can also contain `"sentinel": "MULTIPLE_SELECTION"`.
The marker alone is invalid: provide include/exclude definitions. Empty lists,
tuples, or an empty `ValueOptions` object clear all selections.

Values and range bounds support dynamic providers, evaluated once per occurrence
during screen preparation. Existing `ValueOptions` objects and values returned by
providers are treated as already resolved. `ValueOptions.from_sequence()` applies
the list/tuple shorthand; `ValueOptions.from_dict()` parses explicit options.
Their `resolve=False` option is for already evaluated definitions only. Entries
must resolve to non-empty strings, numbers, or booleans; `None`, empty strings,
nested lists, and malformed range dictionaries are rejected before SAPGUI writes.

**Replacement semantics:** loading multi-selection clears *all* existing include
and exclude entries, including entries supplied by a transaction variant, then
populates the configured selections. Omitted categories are therefore cleared,
not preserved. Use non-indexed `txt`/`ctxt` select-option field IDs; the sibling
multiple-selection button is derived from the field's base identifier.

The implementation targets the standard SAPLALDB dialog: tabs `SIVA`, `INTL`,
`NOSV`, and `NOINT`; subscreens `3010` through `3040`; toolbar button `16` for
Delete All and `8` for confirmation. It checks for the standard include table
before clearing, writes visible table rows, commits full pages with Enter, and
uses the actual scrollbar position after scrolling. Unavailable rows, unexpected
windows, and failures to return to the original window raise errors rather than
silently dropping selections. No clipboard or temporary files are used.

Custom selection dialogs are not supported. These dialog IDs and behaviors are
covered by mock-based tests, **not live SAPGUI verification**. Verify them in your
SAP system before production use, especially Delete All, table expansion across
pages, and selection validation on confirmation. Failures leave the dialog open
for inspection; there is no automatic cancellation or rollback.

A preparation error causes no configured field writes on the affected screen.
This is not rollback: navigation, variant loading, previous screens, and writes
made before a subsequent SAPGUI/COM error may already have occurred. Field errors
preserve their exception causes and use cached status rather than querying SAPGUI
again while handling a failure.

Run the field-processing tests in an environment with the project installed:

```powershell
python -m unittest discover -s tests -v
```