# Workbook controllers

`resin.ao` drives SAP Analysis for Office (AO) macros; `resin.ibp` drives the
IBP COM add-in and, when required, its ribbon. Both use `_workbook` for lifecycle,
deadlines, staging, saving, publication, outcomes, and contextual errors.
This describes the implementation, not certification against an installed SAP
version. See [utilities.md](utilities.md) for field resolution and Windows helpers.

## Imports and configuration

Use `from resin import ao, ibp` and the common outcome/error types exported by
`resin`. Import AO workbook options from `resin.ao.workbook_options`; they are
not re-exported by `ao.__init__`. IBP exports its workbook and connection options;
`ConnectionIdentity` lives in `resin.ibp.connection_options`. Importing the root
package also eagerly imports `gui`; these documents do not cover that subsystem.

Options support `from_dict(data, /)` and inherited `Json.Serial.from_any`.
Dictionary conversion supplies these shared defaults:

| Entry | Default / meaning |
| --- | --- |
| `staging` | Required; converted to `Path`; controller creates a unique run directory beneath it |
| `staging_policy` | `StagingPolicy.ALWAYS` (`"always"`); alternatives `"auto"`, `"never"` |
| `stage_roots` | `[]`, converted to `list[Path]` |
| `cooldown_seconds` | `3600` |
| `poll_seconds` | `0.25` |
| `startup_timeout_seconds` | `90` |

The three timing entries must be positive in dictionary conversion. Direct
dataclass construction requires `staging`, `staging_policy`, and `stage_roots`;
it does not perform the dictionary conversion/validation.

AO adds `addin_name="SapExcelAddIn"` and `ds_alias="DS_1"`. In current refresh code,
the workbook's `ds_alias` is authoritative; the controller option is not a
fallback for it.

IBP adds `addin_name="IBPXLClient.Connect"`,
`connection_mode=ConnectionMode.WORKBOOK`, `anchor_seed=None`,
`anchor_sheetname="Demand View"`, and `stable_seconds=2.0` (positive when parsed).
Dictionary parsing also accepts legacy `anchor` for `anchor_seed`.
`ConnectionOptions(name, planning_area=None, server_url=None, is_default=True)`
describes the requested identity; `is_default` is not used by controller binding.
`ConnectionIdentity(name, planning_area=None, server_url=None, param_str=None)`
is frozen; `from_options` copies the first three fields.

## Shared lifecycle, ownership, and transactions

Controllers are single-use context managers: `NEW -> ENTERING -> READY ->
CLOSING -> CLOSED`, or `FAILED` on startup, invalidation, or failed teardown.
Enter, operations, COM access, and exit must stay on the entering thread.
An operation requires `READY`; concurrent/reentrant workbook operations and
exit during an operation are rejected.

The default `session_factory()` returns `noxl.engines.xlcom.ExcelSession` with
`visible`, `display_alerts`, `screen_updating`, `enable_events`, and `kill_on_exit`
all `True`. The inspected dependency initializes COM on entry and creates Excel
with `DispatchEx("Excel.Application")`, not by attaching to the user's instance.
It closes its registered workbooks, quits Excel, and can terminate its owned PID
on exit. Its save watchdog can also terminate that PID on a hung `Save`.
Custom session factories must implement the operations in `_session_model.Session`
and explicitly establish safe COM/process ownership; borrowing a user's Excel
instance does not make the default session's cleanup safe.

`BaseController(options, session_factory=None, clock=time.monotonic,
sleep=time.sleep, pump=runtime.pump_waiting_messages, now=datetime.now)` exposes:

* `operation(path: Path, timeout_minutes=30)` yields a `WorkbookTransaction`.
  Merely leaving the context does **not** save: call `txn.commit()` explicitly
  for custom operations. Controller `refresh` methods commit on verified success.
* `deadline(timeout_seconds, /, poll_seconds=None)` and
  `wait_for_idle(deadline, /)`; idle means `Excel.Ready` and calculation state `0`.
* `should_stage(path, /)`, `add_stage_roots(*items)` (paths or objects with `.path`),
  `state`, `session`, and `run_directory`.

Transactions fingerprint/copy a staged source, verify the copy, open it writable,
and reject read-only workbooks. `AUTO` stages UNC/HTTPS-like paths and paths under
configured roots; `ALWAYS` stages everything; `NEVER` saves directly to the source.
Successful commit saves within the remaining deadline, closes without another
save, then publishes if staged.

Publication uses a sibling `.<name>.resin-publish.lock`, SHA-256 checks against
the original baseline, a verified sibling copy, a UUID backup
`<stem>.backup.<uuid><suffix>`, and `os.replace`. Backups are retained. The lock
coordinates resin writers, not arbitrary external editors; this is **not** a
remote compare-and-swap or a guarantee of atomicity on every filesystem.
Publication failures retain staging and report recovery/temporary/backup paths.
Failed staged operations also retain their operation directory; cleanup removes
only owned disposable paths, never sweeps the shared staging tree. In-place saves
have no publication backup/rollback.

Cooldown uses the last refresh timestamp, local `now`, and positive configured
seconds. Missing timestamps or `force=True` bypass cooldown. Future timestamps
are logged and treated as zero elapsed time. A cooldown skip still stages/opens,
reads metadata, and closes, but does not commit/save/publish.

## AO API and refresh sequence

Signatures below omit `self`; `/` marks positional-only arguments:

```text
Controller(options, *, session_factory=None, clock=time.monotonic,
           sleep=time.sleep, pump=runtime.pump_waiting_messages, now=datetime.now)
WorkbookOptions(path, id=None, ds_alias=None, columns=None, set_prompts=False)
refresh(wbo, /, set_prompts=None, timeout_minutes=30, force=False,
        *, resolve_prompts=True) -> RefreshOutcome[AoRefreshDetails]
set_variable(key, value, /, ds_alias="DS_1", value_fmt="",
             timeout_seconds=20, poll_seconds=1, *, resolve_value=True,
             _deadline=None, _responses=None) -> int
clear_variable(key, /, ds_alias="DS_1", timeout_seconds=20, poll_seconds=1) -> int
wait_for_ao_ready(timeout_seconds=90, poll_seconds=1) -> None
set_refresh_active_status(status, /, sleep=1) -> None
```

`WorkbookOptions.path` becomes a `Path`; missing/empty aliases use `"DS_1"`.
The default ID is `f(<path stem>)-d(<alias>)`. `columns` raises if unset/empty;
its setter takes an iterable. `detect_columns_from_template(src, *,
sheetname="Sheet1", sep=None)` reads spreadsheet headers through noxl or text
lists through pyqi; it returns a list, rather than assigning `columns`.

**Current initialization caveats:** `WorkbookOptions` neither initializes
`prompts` nor consumes the `prompts` entry in `from_dict`; assign `.prompts`
explicitly when applying prompts. AO controller entry currently calls only the
base no-op startup hook: it does not call `_connect_com_addin` or probe macros.
`ensure_sap_ao_ready(excel, *, timeout_seconds=90, poll_seconds=1,
addin_name="SapExcelAddIn", clock=..., sleep=..., pump=...)` explicitly connects
the exact configured add-in and probes `SAPGetProperty("LastError")`;
`wait_for_ao_ready` waits for Excel idle and probes, but does not connect it.

Example function (syntax-checked only; calling it starts Excel/SAP work):

```python
from resin import ao
from resin.ao.workbook_options import WorkbookOptions

def refresh_ao():
    options = ao.ControllerOptions.from_dict({"staging": "C:\\resin-stage"})
    workbook = WorkbookOptions("C:\\reports\\analysis.xlsm", set_prompts=True)
    workbook.prompts = {"{field_id}": {"sentinel": "CURRENT_DAY"}}
    with ao.Controller(options) as controller:
        ao.ensure_sap_ao_ready(
            controller.session.excel, addin_name=options.addin_name
        )
        return controller.refresh(workbook, timeout_minutes=30)
```

AO refresh activates the workbook, waits for an active/connected datasource with
clear `LastError`, reads `LastRefreshedAt`, and checks cooldown. It then:

1. Executes an initial `SAPExecuteCommand("RefreshData")`; waits for an advanced
   timestamp, datasource readiness, Excel idle, and clear error.
2. Disables refresh behavior and pauses variable submission; sets each requested
   prompt with `SAPSetVariable(key, value, value_fmt, ds_alias)`.
3. Enables refresh behavior and resumes variable submission; verifies the
   pre-final timestamp has not regressed.
4. Dispatches a final `RefreshData`, verifies another timestamp advance, then
   commits. This two-refresh sequence also runs when no prompts are applied.

Command acceptance requires numeric success code `1`; boolean AO properties
accept actual bools or numeric `0`/`1`, rejecting Excel error values.
Recognized busy HRESULTs (`-2147418111`, `-2147417846`, `-2146777998`) are retried
within the deadline. Datasource errors `31`/`32` are treated as unresolved/retryable
during readiness and prompt setting; other errors raise `AoCommandError`.
Failed prompt handling attempts restoration within the **same** deadline;
restoration failure invalidates the controller and does not replace an existing
primary error.

`set_prompts=None` uses `wbo.set_prompts`; false means leave existing prompts
alone, not clear them. `clear_variable` sends an empty string without resolving.
Multi-value prompt arrays currently raise `NotImplementedError` (wrapped inside
an operation). `refresh` resolves each prompt for checking/details even with
`resolve_prompts=False`, and with the default it resolves again inside
`set_variable`; that flag is not a complete bypass or a single-evaluation
guarantee. To send a scalar literally outside refresh, use
`set_variable(..., resolve_value=False)`.

Other public observations: `last_error`, `get_last_error()` (returns a fallback
tuple if unavailable), `changed_datasources`, `changed_crosstabs`,
`is_auto_refresh_active`, `is_connected`, `is_datasource_active(formula_alias, /)`,
`get_crosstab_newline_count(crosstab="Crosstab1", /)`,
`log_datasource_state(ds_alias="DS_1", /, include_last_error=False)`,
`check_workbook_prop(wb_source, prop, /)`,
`get_effective_filters(wb_source, /)`, and `get_last_refreshed_at(target, /)`.
The last three accept AO options (transactionally open/close) or a raw workbook
proxy (activate/read without owning its close). `refresh_data()` and
`open_server_workbook(name, /)` are legacy/deprecated 30-second command helpers.
`AoMacro`, `AoCmd`, `AoProp`, `WorkbookProperty`, and display/object enums name
the SAP strings; availability depends on installed add-in/configuration.

## IBP API, connection binding, and completion

```text
Controller(options, connection_options, api_config=None,
           binding_verifier=naive_binding_verifier, ui=None, backend=None,
           warning_options=None, session_factory=None, clock=time.monotonic,
           sleep=time.sleep, pump=runtime.pump_waiting_messages, now=datetime.now,
           *, verbose=False)
WorkbookOptions(path, sheetname=None, data_origin=None,
                required_headers=None, description=None)
refresh(workbook, /, *, timeout_minutes=30, force=False)
    -> RefreshOutcome[RefreshDetails]
get_workbook_property(wb, prop, /, format_value=WorkbookProperty.default_formatter)
get_last_refreshed_at(wb, /) -> datetime | None
get_connection_name(wb, /) -> str | None
```

IBP workbook defaults are sheet `"Demand View"`, origin `"D4"`, headers `[]`,
description `None`. `data_origin` resolves to `noxl.CellAddress`; `header_origin`
is one row above, `info_addr` two rows above. `with_path(path, /, sheetname=None)`
copies options and deep-copies headers. Refresh uses the path and sheet, not
header validation or data extraction.

Entry connects the configured add-in, stores its `.Object`, waits for Excel idle,
and optionally creates an anchor. `WORKBOOK` checks binding on every target and
can reuse a verifier-approved binding. `ANCHOR` creates a unique workbook in the
run directory (copying `anchor_seed`, or adding a workbook), activates the
configured seed sheet/first new sheet, and forces an initial Connect. It still
verifies every target and can reconnect there; it does not promise one Connect
for the entire controller. The anchor is closed without saving and removed.

`BindingVerifier(requested, active_connection, *, workbook=None, worksheet=None,
connections=None) -> BindingObservation` reports `VALID`, `MISSING`, or `EXPIRED`.
The controller currently passes workbook/worksheet but not `connections`.
`VALID` requires an identity with a nonempty name and no conflict with specified
name/planning area/server URL. The intended verifier contract is proof of both
identity and usable authentication. The shipped `naive_binding_verifier` only
checks that active connection text contains all configured planning-area/URL
substrings: it is **not** authentication/version proof, and needs at least one
such substring. Prefer a verifier tested against your installed IBP API.

With `binding_verifier=None`, the controller never reuses binding: it Connects,
then requires a truthy active connection and matching workbook connection name.
Connect is attempted once, with an optional version-warning watcher around it;
post-Connect binding failure raises `ConnectionBindingError`.
The controller's configuration/PID-scoping checks are in `__post_init__`, but
the regular (non-dataclass) controller does not call it automatically.
Supply a nonempty connection name, compatible verification options, and
process-scoped warning criteria yourself.

Example using explicit no-reuse verification (calling it drives Excel/ribbon):

```python
from resin import ibp

def refresh_ibp():
    options = ibp.ControllerOptions.from_dict({"staging": "C:\\resin-stage"})
    connection = ibp.ConnectionOptions(name="Configured SAP connection")
    with ibp.Controller(
        options, 
        connection, 
        binding_verifier=None
    ) as controller:
        controller.warning_options["process"] = controller.session.pid
        return controller.refresh("C:\\reports\\planning.xlsm")
```

IBP refresh acquires a process-local module `RLock` under the operation deadline,
activates workbook/sheet, reads metadata and cooldown, verifies/connects binding,
then takes the maximum pre/post-connection timestamp as completion baseline.
It dispatches `ibp.Refresh()` if `api_config.refresh_enabled`, otherwise
`RefreshUI.refresh(...)`. A timestamp newer than baseline must remain unchanged
for `stable_seconds` while Excel is idle; returning from dispatch is not success.
Dispatch/completion failures invalidate the controller. The UI lock is released
before commit/publication; it does not permit cross-thread controller use or
serialize Excel in other processes.

`GlobalConfiguration` defaults both `EXCEL_PLANNING_VIEW_APIS` and
`EXCEL_MASTER_DATA_APIS` to `"none"` and *describes*, rather than changes, SAP policy.
**Current code caveat:** `refresh_enabled` tests the *master-data* entry against
planning-view authorization (`"read"`, `"simulate"`, `"save"`), not the
planning-view entry. Do not assume setting planning-view permission alone selects
COM refresh. `RibbonRefreshUI(ribbon_tab_title="SAP IBP",
refresh_btn_title="Refresh")` uses UIA, PID-scoped application connection,
workbook-title regex or supplied handle, focus, and input clicks.
The controller's `backend` option is stored but not forwarded to this UI call.

Properties read defined names such as `SOP_Connection_Name` and
`SOP_Refresh_Timestamp`: first `RefersToRange.Value`, then scalar `.Value` for
the Excel object-error case. The default formatter unwraps `="..."` and doubled
quotes. Property/timestamp readers also handle paths/options internally by
opening a transaction; raw workbook proxies remain caller-owned.

## Outcomes, deadlines, and errors

`RefreshOutcome` is frozen and records `status`, original `path`, `operation_id`,
start/end/elapsed time, previous/new timestamps, `publication`, `details`,
`skip_reason=None`, `cooldown_remaining_seconds=0.0`, and `message=None`.
Statuses are only `"refreshed"` and `"skipped_cooldown"`; failures raise.
Publication is `"not_attempted"`, `"in_place"`, or `"published"`.
AO details hold datasource, applied prompt keys, response tuples, completion and
live-semantics flags (the latter remains false), and best-effort source metadata.
IBP details hold requested/observed identities, Connect/reuse flags, and disposition.

Read attributes for complete structured results. Current `RefreshOutcome.to_dict`
omits operation ID, elapsed time, and new timestamp, and stringifies details.
`AoRefreshDetails.to_dict` uses `list[self.responses]` rather than a normal list,
so its string/JSON representation is not a dependable serialization interface.

`Deadline(seconds, *, clock=time.monotonic, sleep=time.sleep,
pump=runtime.pump_waiting_messages, poll_seconds=0.25)` shares one monotonic budget.
`remaining()` raises when expired; `check(phase="operation")` adds phase;
`pause(seconds=None)` pumps and sleeps no longer than the remaining budget.
Startup defaults to 90 seconds and refresh to 30 minutes; the budget includes
lock waits, staging, COM, completion, save, and publication. Checks around calls
do not interrupt a blocking COM call, file copy, or OS operation. Save has the
dependency's owned-PID watchdog; other waits are cooperative, not hard cancellation.

`WorkbookControllerError(RuntimeError)` exposes `.context`; `add_context` keeps
existing keys and adds exception notes. Subclasses:
`ConfigurationError` (also `ValueError`), `ConnectionBindingError`,
`ExcelComValueError`, `RefreshTimeoutError` (also `TimeoutError`),
`WorkbookIOError`, `PublicationError` (an I/O subtype), and `DeadSessionError`.
AO adds `AoCommandError`. Operation failures attach phase, operation ID, paths,
PID, and last timestamp; publication errors add backup/temporary/recovery paths.
Unexpected errors are wrapped as I/O or dead-session errors with their cause.
Fatal RPC/disconnected HRESULTs, `DeadSessionError`, and noxl
`ExcelSaveTimeoutError` invalidate the session; create a new controller afterward.

Timestamp parsing accepts missing/zero values, unzoned datetimes, and nonnegative
Excel serial numbers/numeric formula literals, not ISO date strings. Both
controllers honor `Workbook.Date1904`; see utilities for the exact parser.
These examples were syntax-checked only: Excel/SAP readiness, UI selectors,
authentication, remote publication semantics, and installed-version completion
behavior require live environment validation.
