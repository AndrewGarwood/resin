# SAP GUI architecture and session pools

`resin.gui` wraps the Windows SAP GUI Scripting COM API. It is not a GUI
toolkit: it locates existing SAP objects, interacts with their controls, and
coordinates transaction work across sessions. SAP GUI must be installed and
scripting enabled on the client and server. Attaching does not log in, enable
scripting, or handle authentication dialogs.

This guide covers core wrappers, components, GUI-ID utilities, all GUI data
models, and session provisioning/pooling. Transaction execution and export
service internals belong to the companion transaction/export documentation.
For save-dialog behavior, lifetime requirements, and controlled live
diagnostics, see [SAP GUI save dialogs](sapgui-save-dialogs.md).

## Layers and identity

```text
Application -> Connection -> Session -> Component / Container
                    stable SapContext IDs
                              |
                         ComGateway
                              |
              SAPGUI.GetScriptingEngine / Children / FindById

SessionProvisioner -> SessionProvisioningResult
                       | bindings + connection lease
                   SessionPool
                       | one SessionWorker per binding
                       | PREPARE / EXECUTE / POST_EXECUTE / EXPORT
                   Transaction methods on each worker's Session
```

### `SapContext`

`SapContext` is a frozen, slotted dataclass with optional `application_id`,
`connection_id`, `session_id`, and `component_id`. It contains no COM objects.
Non-`None` IDs must be nonempty strings. A session requires a connection; a
component requires a session. It does **not** validate the syntax of an ID or
prove that the object exists.

Typical runtime IDs are `/app`, `/app/con[0]`, and
`/app/con[0]/ses[0]`. Component lookup also accepts session-relative IDs such as
`wnd[0]/usr/ctxtWERKS-LOW`. These slashes are **SAP ID syntax**, not filesystem
path separators.

The `with_*` methods return replacement contexts:

* `with_application(id)` preserves the other IDs.
* `with_connection(id)` clears session and component IDs.
* `with_session(id)` requires a connection and clears the component ID.
* `with_component(id)` requires a connection and session.

`require_connection()`, `require_session()`, and `require_component()` return
respectively an ID, a two-ID tuple, and a three-ID tuple, or raise
`SapInvalidContextError`. The corresponding `get_*_id()` methods return the
individual ID.

### `ComGateway`

`ComGateway(*, prog_id="SAPGUI", logger=None)` is the COM boundary.
`get_application()` calls `win32com.client.GetObject(prog_id)` and reads
`GetScriptingEngine`. Every subsequent resolution walks back through that
engine; the gateway retains neither the engine nor child dispatch objects.
There is no engine-cache API.

* `get_connection(connection_id)` enumerates application children.
* `get_session(connection_id, session_id)` enumerates connection children.
* `find_component(connection_id, session_id, component_id,
  raise_on_missing=True)` calls `session.FindById(component_id, False)`, with
  a one-argument compatibility fallback.
* `component_exists(...)` performs nonraising component lookup.
* `get_property(dispatch, prop, factory=None, *, default=None, source=None,
  _raise=False)` reads a dynamic property and optionally converts it.

Dispatch validation is structural (`Id` and `Type`), not a strict
`CDispatch` check. Expected application, connection, and session types are
checked when available. Missing components can return `None`; nonraising
lookup also suppresses some `FindById` failures, but failure to resolve the
parent connection/session can still raise. A property default handles an
absent attribute, not every COM getter or conversion error.

The older `resin.gui.com.get_application_com()` helper is different: it
launches `AppManager.exe()`, requires concrete `CDispatch` objects, and returns
a raw application dispatch. It does not provide a managed cache.

### COM apartments and ownership

Use `resin.utils.runtime.com_apartment()` around COM work on the calling
thread. It balances `pythoncom.CoInitialize()` and `CoUninitialize()` even
when work raises. **There is no `ComGateway.com_apartment()` method.**
`resin.gui.com.runtime` only provides its older message-pump helper; core
connection polling uses `resin.utils.runtime`.

Do not pass raw COM objects between threads. Core/component wrappers retain
IDs and resolve dispatch objects on each operation, but that does not make
simultaneous interaction with the same SAP session safe. Prefer one worker
per session. Retain locators/bindings, rather than a worker's resolved session
or `session.info`, as cross-thread identity.

Export invocation has an intentional **scoped lifetime exception**: the
toolbar, context-menu, and keyboard-shortcut export methods use the private
`_retain_scripting_session` context manager to hold a raw `GuiSession` on the
calling thread throughout invocation and save-dialog handling. This is not
an engine cache or permission to share dispatch objects between threads.
Controlled LX02 diagnostics found that retaining the application alone did
not prevent a native save dialog, whereas retaining the session produced the
SAP dialog. All three updated export methods produced the SAP dialog without
an extra caller-managed reference.

The native-save fallback also waits up to five seconds for an Edit control
to become ready; finding the dialog window alone does not prove its filename
control is ready. See [SAP GUI save dialogs](sapgui-save-dialogs.md) for the
diagnostic evidence and fallback constraints.

The following reads an existing session; the connection index and field ID
must match the actual SAP screen. It neither creates a connection nor sets
the field:

```python
from resin.gui import Application, ComGateway, CTextField, GUI
from resin.utils import runtime

with runtime.com_apartment():
    app = Application.attach(ComGateway())
    connection = app.get_connection(0)
    session = connection.get_session(0)
    SessionType = type(session)
    SessionType.wait_for_idle(session)
    field = session.find(
        GUI.ctxt(GUI.usr(0), GUI.lowerbound("WERKS")),
        component_cls=CTextField,
        _raise=True,
    )
    print(field.diagnostic_state())
```

## Application, connection, and session

### `Application`

`Application.attach(gateway=None)` attaches to a running scripting engine; it
does not launch SAP Logon. The constructor accepts `gateway=` and optional
`context=`; without a context it resolves the engine immediately.

`connections` returns a tuple snapshot of wrappers, not a live COM collection.
`connection_count` and `total_session_count` make fresh reads.
`get_connection(index=0)` uses snapshot indexing. `find_connection(...)`
requires at least one criterion, applies all supplied criteria with exact
equality, and returns a match or `None`; `require_connection(...)` raises if
none matches. Criteria are `connection_id`, `description`, `runtime_name`,
`runtime_id`, and `connection_string`. **`Connection.runtime_id` is not
implemented**, so using that criterion currently produces no match.

`open_connection(description, *, sync=True, raise_on_error=True,
enforce_session_capacity=True)` opens a SAP Logon description.
`open_connection_by_string(connection_string, *, synchronous=True,
raise_on_error=True, enforce_session_capacity=True)` uses a technical
connection string. Both check the configured application capacity by default
and return a wrapper. Neither is a login workflow. `refresh()` verifies engine
availability and refreshes the application context.

### `Connection`

`Connection(*, gateway, context, session_capacity=None)` requires a connection
context and removes any session context. Its capacity is captured at
construction from `AppManager` unless explicitly supplied.

| API | Behavior |
| --- | --- |
| `application` | Parent application wrapper |
| `sessions`, `session_count` | Fresh tuple snapshot / COM child count |
| `get_session(index=0)` | Snapshot indexing |
| `find_session(id)`, `require_session(id)` | Exact ID lookup; optional / raising |
| `description`, `connection_string`, `runtime_name`, `disabled_by_server` | Fresh COM properties |
| `assert_session_capacity(limit=None)` | Rejects creation when current count is at least the limit |
| `wait_for_session_capacity(*, limit=None, timeout=300.0, poll_interval=1.0)` | Waits for count below the limit; returns the connection |
| `create_session(*, source_session=None, limit=None, timeout=15.0, poll_interval=0.1)` | Calls `CreateSession()` on a source session and returns the first previously unseen runtime ID |
| `close_session(session)` | Accepts a `Session`, nonempty ID string, or nonnegative integer (`ses[n]`) |
| `close()` | Closes the entire connection and all its sessions |

Creation requires an existing source session. If omitted, the first existing
session is used; a supplied source must belong to this connection. Discovery
uses an ID set difference, not the position of the last child. The capacity
check here is connection-local; it does not separately check total application
capacity. Polling uses positive timeout/interval values, monotonic deadlines,
message pumping, and bounded sleeps.

If a newly created session needs explicit cleanup, retain its returned
wrapper and call `created.close()` in `finally`. This delegates to
`connection.close_session(created)` with a connection-ownership check.
Closing a window/session/connection does not handle SAP confirmation dialogs.

### `Session`

`Session(gateway, context)` requires connection/session IDs and drops a
component ID. `_com` resolves the current session each time; `connection`
and `parent` return connection wrappers.

* `busy`, `is_active`, `passport_transaction_id`, `active_window`,
  `main_window`, `statusbar`, and `transaction` read current state.
* `info` returns **raw `GuiSessionInfo` COM**, not a `SessionInfo` dataclass.
  `SessionInfo` exists separately as a frozen, slotted DTO with transaction,
  response time, system/session/user/client/server/screen fields.
* `find(id, *, component_cls=None, _raise=False)` comes from `FindMixin`.
  Lookup uses the component registry unless a wrapper class is explicitly
  requested. An explicit class must extend `Component`, but its SAP type is
  not verified.
* `exists(id)` performs nonraising component lookup.
* `press_button(id, *, timeout=5.0)`, `set_field_value(id, value, field_cls,
  timeout=5.0)`, and `select_radio_option(id, *, option=None, timeout=5.0)`
  locate controls and perform their actions. `field_cls` is a text-field or
  checkbox wrapper; radio options may be supplied or inferred from a final
  `radOPTION` stem.
* `send_command(command)`, `start_transaction(code)`, and
  `end_transaction()` return the session. They do not implicitly wait for
  server completion.
* `get_object_tree(component_id="", *, properties=None)` returns SAP's JSON
  object-tree string.
* `raise_on_error()` raises `SapGuiStatusError` only for message type `"E"`,
  carrying text, message ID/number, and session ID. It does not automatically
  raise for warning or abort messages.
* `close()` delegates to connection-level session closure.

`Session.wait_for_idle(session, *, timeout=60.0, poll_interval=0.05)` is a
**static method**: pass the session explicitly. It returns the session when
idle and raises `TimeoutError` if it remains busy.
`session.wait_for_component(...)` defaults to `_raise=False`,
`timeout=5.0`, and `poll_interval=0.1`; see the polling caveat below before
relying on missing-component retries.

## Components and dispatch wrapping

`Component(*, gateway, context)` requires a component identity. It exposes
`name`, `type`, `type_as_number`, `container_type`, `parent`, `session`,
`exists()`, and `diagnostic_state(properties=...)`. `_resolve()` and `_com`
perform fresh `FindById` lookup. `com_parent` is a raw COM escape hatch;
`parent` attempts to wrap that dispatch as a component, so it is not a
universal navigation API for noncomponent parents.

`VComponent` adds `text`, `changeable`, `enabled`, `tooltip`, `dump_state()`,
`set_focus()`, and `visualize()`. `Container` combines `Component` with
`FindMixin`, adds immediate-child tuple snapshots and `iter_children()`,
and supports `exists()` for itself or `exists(component_id)` for another
session-relative ID. Container lookup does not automatically prepend the
container's ID. `VContainer` is a container subclass; it does **not** itself
inherit the `VComponent` visual-property helpers.

`components.factory.wrap_dispatch(dispatch, gateway, context)` reads SAP
`Type` and `Id`, constructs a component context, and selects a registered
wrapper or generic `Component`. `register_component()` maps a class name
to `Gui<ClassName>` (or preserves a name already starting with `Gui`);
duplicate registrations of a different class raise. `registered_components()`
returns a copy of the registry.

| Wrapper | Operations of interest |
| --- | --- |
| `TextField`, `CTextField` | `get()`, `set(value)`, `clear()`, writable `text`; `None` becomes `""`. An unchangeable field only accepts an already-equal value |
| `CheckBox` | `selected` property and `set(bool)` |
| `RadioButton` | `select()`, `group_members`, `group_count` |
| `Button` | `press()` |
| `Tab`, `TabStrip` | Tab selection/scrolling; tab-strip child snapshots |
| `Label` | `get_list_property(prop)` |
| `UserArea` | Container wrapper |
| `Shell` | Context-menu selection by code, position, or text; `handle`, `sub_type` |
| `GridView` | Toolbar/context-menu actions, selection/clicks, row count/title/column order, row lookup |
| `TableControl` | `visible_row_count`, `first_visible_row`, `scroll_to(row)` |
| `FrameWindow`, `MainWindow`, `ModalWindow` | Virtual keys, maximize/restore/close/handle; main-window pane resizing |
| `Statusbar` | Message type/ID/number, popup/long-text flags, classification and diagnostic status |

Some controls return their session (`Button.press`, field/checkbox setters);
others return themselves or `None`. Do not assume uniform fluent chaining.
Table scrolling can invalidate a dispatch: reacquire through the wrapper
after every scrollbar change.

The factory dispatches on `Type`, not `SubType`. A `GuiShell` whose subtype
is `GridView` is therefore normally wrapped as `Shell`, not `GridView`.
For a known ALV grid, request `component_cls=GridView` explicitly.
`TabStrip` is registered but is not re-exported by `components.__init__`;
import it from `resin.gui.components.control`.

`busy_safe(wait_before=True, wait_after=False)` decorates selected control
methods. It uses a per-session reentrant lock, a legacy idle wait
(`60.0` seconds / `0.05` polling), and short message-pumping waits before and
after the action. It does not initialize COM, does not decorate every action,
and wraps failures in `RuntimeError`. It is not a substitute for exclusive
session ownership.

## Provisioning, leases, and worker lifecycle

### Configuration

`AppManager` is process-wide class state, not per-pool configuration:

| Setting | Default / setter |
| --- | --- |
| Application total session capacity | `6`; `set_session_capacity(value)` |
| Connection session capacity | `6`; `set_connection_session_capacity(value)` |
| Strict capacity validation | `True`; `set_strict(bool)` |
| Verbosity flag | `False`; `set_verbose(bool)` |
| SAP Logon executable | `C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe`; `set_exe(str_or_Path)` |

Strict mode rejects configured capacities above six. Raising these local
limits does not increase SAP's server-side session limit. Existing connection
wrappers retain their captured capacity; later wrappers use the new setting.
The verbosity flag is exposed as state, not a guarantee that every service
changes its logging behavior.

`ConnectionOptions` is a frozen, slotted configuration DTO with optional
`index`, `id`, `description`, and `string`, all defaulting to `None`.
`from_dict` copies these values without comprehensive type validation.

Actual `SessionProvisionerOptions` defaults are:

| Field | Default |
| --- | --- |
| `session_count` | `1` |
| `connection` | `ConnectionOptions()`; a selector must still be supplied |
| `launch_if_unavailable` | `True` |
| `attach_timeout`, `attach_poll_interval` | `30.0`, `0.25` seconds |
| `create_timeout`, `create_poll_interval` | `15.0`, `0.1` seconds |
| `close_created_sessions_on_exit` | `True` |
| `close_opened_connection_on_exit` | `True` |

Construction validates positive counts/time values and requires a connection
selector. Consequently **`SessionProvisionerOptions()` alone raises** despite
its dataclass defaults. `from_dict` requires `session_count`; missing/invalid
configuration is wrapped in `RuntimeError`. Stale source docstrings describing
launch/connection cleanup as defaulting to `False` are not the implementation.

This example only parses configuration; it performs no SAP work:

```python
from resin.gui import SessionProvisionerOptions, SessionPoolOptions

provision_options = SessionProvisionerOptions.from_dict({
    "session_count": 2,
    "connection": {"index": 0},
    "launch_if_unavailable": False,
    "close_created_sessions_on_exit": True,
    "close_opened_connection_on_exit": False,
})
pool_options = SessionPoolOptions.from_dict({"execute_timeout": 600.0})
```

### Provisioner flow

`SessionProvisioner(options, *, gateway_factory=ComGateway, launcher=None,
connection_bootstrapper=None).provision()` runs in a temporary COM apartment
and returns a `SessionProvisioningResult`, not live core wrappers.

1. Attach to the engine. If unavailable and launching is allowed, a
   **supplied** `launcher()` is required; there is no implicit launcher.
   `default_sap_gui_launcher()` launches the configured executable and sleeps
   two seconds. Attachment then uses the configured polling timeout.
2. The provisioner itself sleeps two seconds after attachment, even if SAP
   was already running.
3. Resolve an existing connection. If `id` is supplied, that lookup returns
   immediately (including no match). Otherwise try `description`, then
   `string`, then `index`. These are selection priorities, not an AND search.
4. If no match exists, use a supplied `connection_bootstrapper(application)`,
   otherwise open by description or technical string. An unmatched index/ID
   alone cannot open a connection. Authentication remains the caller's job.
5. Borrow the first existing sessions up to the requested count; create only
   the deficit, using the first selected session as source.
6. Return exactly the requested count with unique connection/session pairs.
   There is no preflight reservation or rollback of sessions/connections
   already created if later provisioning fails.

The result holds `bindings`, a `connection` lease, reused/created counts, and
`launched_application`; `session_count`, `connection_id`, and `application_id`
are convenience properties. **`opened_connection` reports
`connection.close_on_exit`**, not an independent record that a connection
was opened: opening with cleanup disabled yields `False`.

### Cleanup ownership

`SessionLocator(connection_id, session_id, application_id=None)` and
`ConnectionLocator(connection_id, application_id=None)` are immutable IDs.
`resolve(gateway=None)`/calling a locator constructs a wrapper; actual
existence is checked by subsequent COM reads.
`SessionBinding(locator, close_on_exit=False)` and
`ConnectionLease(locator, close_on_exit=False)` add cleanup policy.

| Provisioning situation | Shutdown owner |
| --- | --- |
| Existing connection and existing session | Borrowed; neither is closed |
| Created session, connection not owned | Worker closes it when `close_created_sessions_on_exit=True` |
| Newly opened connection with `close_opened_connection_on_exit=True` | Pool closes the connection after workers stop; all session bindings are normalized to `close_on_exit=False` |
| Newly opened connection with connection cleanup disabled | Connection remains; existing/bootstrap session remains, while created sessions follow their individual cleanup policy |

Connection ownership overrides per-session cleanup to avoid double closure.
Closing an owned connection closes **every** session then under it, including
sessions not selected for this pool. Launched SAP Logon itself is not an
owned process that the provisioner shuts down.

### Pool construction and execution

`SessionPool(bindings, options=None, *, connection_lease=None)` requires at
least one binding and rejects duplicate `(connection_id, session_id)` pairs.
A supplied connection lease must match all bindings. Construction creates
worker objects but does not start their threads.

Construction helpers:

* `from_provision_result(result, *, options=None)` preserves the bindings and
  connection lease.
* `from_provisioner(provisioner, *, options=None)` provisions immediately.
* `bootstrap(session_count, options=None, connection_options=None,
  provisioner_options=None, launch_if_unavailable=False, launcher=None)`
  provisions immediately. Supply a real connection selector: its default
  empty `ConnectionOptions()` is invalid. Explicit `provisioner_options`
  takes precedence over the separate count/connection/launch arguments.
  Bootstrap's default launch flag is `False`, unlike the provisioner DTO.
* `from_locators(locators, *, options=None, close_on_exit=False)` binds
  already-existing sessions without provisioning a connection.

`start()` is idempotent on a started pool, and rejects a closed pool.
The context manager starts on entry and closes on exit. `size` and `workers`
expose the fixed worker set. `run(transactions, *, return_dict=False,
key_normalizer=None)` requires a started pool, rejects duplicate transaction
IDs, and accepts initial stages `CREATED` or `COMPLETED`.

Scheduling is **batch-based**, not work stealing: a batch contains at most
~~one transaction~~ per worker, and the next batch waits for the entire current
batch. Each batch executes these barriers:

| Command phase | Required stage after phase |
| --- | --- |
| `PREPARE`: `open(session)` then `populate_selection_screen(session)` | `READY_TO_EXECUTE` |
| `EXECUTE`: `execute(session)` | `POST_EXECUTE` |
| `POST_EXECUTE`: `handle_post_execute(session)` | `READY_TO_EXPORT` or `COMPLETED` |
| `EXPORT`: `export(session)` for those still needing export | `COMPLETED` |

The first three phases run in parallel across workers. Exports are submitted
and awaited **one at a time** within this pool; already-completed transactions
skip export. A failure aborts `run()` rather than guaranteeing a partial
result list. Successful list results preserve input order via
`transaction.get_result()`. Dictionary mode delegates to `build_result_dict`;
the optional normalizer transforms transaction-result IDs into keys.

For caller-supplied `Transaction` objects, this selects up to two existing
sessions from a specific connection and borrows them. It still changes those
sessions' screens: only select sessions reserved for this work.

```python
from resin.gui import SessionPool, SessionPoolOptions, discover_session_locators


def run_on_existing_sessions(transactions, connection_id):
    locators = [
        locator for locator in discover_session_locators()
        if locator.connection_id == connection_id
    ][:2]
    if not locators:
        raise RuntimeError("No sessions found for the selected connection")
    with SessionPool.from_locators(
        locators, options=SessionPoolOptions(), close_on_exit=False,
    ) as pool:
        return pool.run(transactions)
```

Convenience functions `discover_session_locators()` and
`discover_session_bindings()` inspect all open connections inside a temporary
COM apartment; discovered bindings are borrowed.
`provision_session_bindings(count, *, connection_index=0,
close_created_sessions_on_exit=True)` is the simpler existing-connection
helper: it borrows existing sessions and creates the deficit, without the
provisioner's launch/connection-lease machinery.

### Workers, timeouts, and failures

`SessionWorker(worker_id, binding)` owns one **non-daemon** thread and a FIFO
command queue. Startup initializes COM, constructs its session wrapper, and
validates the session through the gateway without retaining the dispatch.
Commands for that session execute serially and complete a `Future`.
Command exceptions are put on the future; they do not ordinarily terminate
the command loop. The worker tracks its current transaction until terminal.
COM messages are pumped after commands, not continuously while the worker
blocks waiting for its next queue item.

`start(timeout=30.0)` waits for readiness; `submit(command_type, transaction)`
requires readiness. `stop()` enqueues a `STOP` command behind queued work and
returns a future; `join(timeout=None)` waits for thread termination and raises
if still alive. Session cleanup runs inside the worker's COM apartment.
`SessionWorker`, `SessionCommand`, and `SessionCommandType` are available from
their defining modules, not directly from `resin.gui`/the pool facade.

| `SessionPoolOptions` field | Constructor default | `from_dict` missing-key default |
| --- | --- | --- |
| `worker_start_timeout` | `30.0` | `30.0` |
| `stop_timeout` | `30.0` | `30.0` |
| `prepare_timeout` | `120.0` | `120.0` |
| `execute_timeout` | **`600.0`** | **`900.0`** |
| `post_execute_timeout` | `120.0` | `120.0` |
| `export_timeout` | `300.0` | `300.0` |

Phase timeout `None` means no deadline. The DTO does not validate all timeout
values; `from_dict` replaces falsy worker-start/stop values with `30.0`.
The first three phase deadlines apply to the whole group of submitted
futures, not independently per transaction. The export deadline applies to
each sequential export. Shutdown applies `stop_timeout` to individual future
waits and joins, not one global deadline.

`wait_for_commands` waits for all futures. Unfinished work produces
`TimeoutError` listing transaction IDs; completed failed commands produce
`SessionPoolError`, whose `errors` is a tuple of `(ID, exception)` pairs.
Stage checks can separately raise `RuntimeError`.

**Timeouts do not cancel commands, interrupt COM calls, or kill threads.**
After a phase timeout a worker may still be running. Shutdown requests all
stops, waits for their futures, then joins; an owned connection is only closed
if no workers remain alive. Shutdown failures are aggregated, and the pool
is marked closed even if cleanup failed.

Worker cleanup has a further limitation: an owned-session close failure is
stored as worker `_fatal_error`, but ordinary `join()`/pool shutdown does not
surface that stored error. The STOP future is completed before session
cleanup. Startup timeout cleanup is also not a cancellation mechanism; a
worker that times out during initialization can remain alive. Reserve sessions
carefully and verify actual SAP state after failed/timed-out cleanup.

## Transaction and export data models

These objects describe configuration/results; constructing them does not
execute transactions or export files. Most inherit `pyqi.Json.Serial` and
provide `from_dict`/`to_dict`; parsing is not uniform schema validation.
Frozen DTOs do not make nested mutable objects immutable.

### Transaction options

`TransactionOptions` is a mutable dataclass:

| Field | Meaning / default |
| --- | --- |
| `code` | Required transaction code |
| `_id` | Optional constructor ID; dictionary key is `id` |
| `method` | `ExecutionType.STANDARD`; values `standard`, `async`, `custom` |
| `fields` | Fresh dictionary of first-screen field definitions |
| `layout` | Optional `LayoutOptions(field_id, name)` |
| `variant` | Optional `VariantOptions(name, created_by)` |
| `export` | Optional `ExportOptions` |
| `screens` | Fresh list of `ScreenFieldSelection` |

`from_dict` resolves execution method enums and nested DTOs. `fields` holds
definitions for later transaction-service resolution; the DTO itself does
not evaluate dynamic field values.
`with_fields(mapping, copy_existing=False)` returns a replacement with a new
field dictionary and a shallow-copied screen list; by default it replaces,
not merges, the first-screen fields. Nested layouts/export/screens remain
shared. `set_export_path(path=None, *, ref_date, dt_fmt=None)` mutates the
nested file path and returns the resulting `Path`; `ref_date` is a required
keyword even when its value is `None`.

`LayoutOptions.from_dict` accepts `name` or legacy `variant`;
`.variant` aliases `.name`. `VariantOptions.from_dict` requires both name
and creator.
`ScreenStep(vkey=None, button=None)` is frozen and requires at least one
non-`None` action; it permits both. `ScreenFieldSelection` has required
`step_in`, mutable `fields`, and optional `step_out`.
Its parser defaults a missing/falsy `step_in` to virtual key `5`
(`TXN_NEXT_SCREEN`) and missing fields to `{}`. `with_fields` replaces/merges
its own field dictionary; `set_field(key, value)` mutates it.

This is a configuration-shape example, not a certified transaction/screen.
Replace the code, IDs, and export method with those supported by your SAP
transaction:

```python
from resin.gui import TransactionOptions, GUI

options = TransactionOptions.from_dict({
    "code": "YOUR_TRANSACTION",
    "id": "selection-demo",
    "method": "standard",
    "fields": {GUI.ctxt(GUI.usr(0), GUI.lowerbound("WERKS")): "plant_id"},
    "screens": [{"step_in": {"vkey": 5}, "fields": {}}],
    "export": {
        "method": "keyboard_shortcut",
        "invoke": {"vkey": 16},
        "file": {"path": r"C:\\reports\\selection.xlsx"},
        "overwrite": False,
    },
})
updated = options.with_fields({"wnd[0]/usr/chkP_FLAG": True}, copy_existing=True)
```

`TransactionStage` defines `CREATED`, `OPENING`, `POPULATING_SELECTION`,
`READY_TO_EXECUTE`, `DISPATCHING_EXECUTE`, `EXECUTION_RUNNING`, `POST_EXECUTE`,
`READY_TO_EXPORT`, `EXPORTING`, `COMPLETED`, and `FAILED`. These are execution
state, not additional transaction options.

### Export options

| Model | Actual fields/defaults |
| --- | --- |
| `ExportOptions` | `method=ExportMethod.NONE`, `layout=None`, fresh `invoke`, `file`, `save`, `overwrite=False` |
| `ExportMethod` | `none`, `context_menu`, `toolbar_button`, `keyboard_shortcut`; no implemented toolbar-context enum value |
| `InvokeMethodOptions` | Optional `button_id`, `vkey`, `grid_id`, `menu_item_id`, `menu_item_position`, `menu_element_class` |
| `FileOptions` | Path default `export.xlsx`; constructor accepts `path`, `outdir`, `name`; properties `path`, `dir`, `name` |
| `SaveDialog` | Default directory `wnd[1]/usr/ctxtDY_PATH`, filename `wnd[1]/usr/ctxtDY_FILENAME`, confirm `wnd[1]/tbar[0]/btn[0]` |
| `LayoutSelector` | Required `name`, `grid_id`, and truthy `button_id` or `vkey`; `iter_reverse=False`; constructor `button_id` is stored as `.btn_id` |

`InvokeMethodOptions.from_dict` also accepts a button-ID string, numeric string,
or nonnegative integer virtual key. Use a mapping for key `0` inside
`ExportOptions`: a bare falsy `invoke=0` is treated as absent by that parser.
`LayoutSelector` uses truthiness for its action requirement, so `vkey=0`
alone is rejected.

`FileOptions.from_dict` accepts `dir`, `parent`, or `outdir` as directory
aliases. Directory plus name wins when supplied with a path; avoid ambiguous
combinations. There is no `.outdir` property despite the dictionary key.
`formatted_path`/`get_formatted_path` optionally apply a reference date
(`None`/`"none"`, `"today"`, or a resolvable date), default date format
`YMD_DOT`, filename rename behavior, and then Python `str.format`.
Formatting returns a `Path`; it does not create a file.

### Results

* `ExportDetails(path=None, row_count=None)` describes export output.
* `CompletedExport` adds `tel: pyqi.Telemetry`. `from_details(details, tel)`
  copies the output description; `to_dict()` serializes path/count/telemetry.
  `path_exists()` checks that a non-`None` path is currently a file, not that
  its contents or workbook are valid.
* `TransactionDetails(txn_id, code, exec_tel, exported=None, status=None)`
  serializes transaction execution telemetry, optional completed export,
  and status. `has_been_exported` depends on `exported.path_exists()`.
* Pool results use **`pyqi.Result[TransactionDetails]`**. There is no concrete
  exported `TransactionResult` or `ExportResult` class in these model modules.

Material serialization limitations: `TransactionOptions.to_dict()` currently
omits `fields`, so it is not a lossless configuration round trip.
`LayoutSelector` inherits generic serialization that currently omits its
required `name` and `grid_id` and emits `.btn_id`, whereas its parser reads
`button_id`; do not assume all nested option objects round-trip identically.
Keep the original configuration when fidelity matters.

## GUI-ID helpers

`resin.gui.GUI` aliases `resin.gui.utils.gui_id`. These are string builders,
constants, enums, and a stem parser, not SAP metadata discovery.

| Group | Examples |
| --- | --- |
| Basic IDs | `wnd`, `btn`, `tbar`, `sbar`, `usr`, `chk`, `shell`, `tbar_btn`, `ctxt`, `txt`, `lbl`, `tabp`, `okcd`, `ssub`, `tblSAPLALDB` |
| Selection bounds | `lowerbound(field)`, `upperbound(field)` |
| Path parts | `join`, `parent`, `stem`, `replace_stem`, `replace_window`, `get_container_index`, `get_window_index`, `field_type` |
| Known SAP dialogs/actions | `txn_variant_name`, `txn_variant_created_by`, `cntl_grid`, export-dialog builders, `execute_txn_btn` |
| Multi-selection tables | `cell_index_suffix`, `ctxt_cell_id`, `ctxt_single_value_field_id`, `ctxt_interval_field_id` |

`usr()` defaults to `"usr"` (not `"wnd[0]/usr"`); `usr(0)` includes the
window. `ctxt(None, field)` produces `"ctxt/field"`, while `txt(None, field)`
produces `"txtfield"`; use an explicit parent for normal screen fields.
`join` trims whitespace and trailing slashes, not every leading slash.
`get_container_index`/`get_window_index` match at the beginning of the ID,
so a fully qualified `/app/.../wnd[0]/...` ID does not yield a window index.

`VKey` contains SAP virtual-key values and action aliases, notably Enter `0`,
execute `8`, variant selection `17`, and default export `16`.
`BaseField` contains common field stems. Multi-selection enums describe
include/exclude single-value/interval tab IDs (`SIVA`, `INTL`, `NOSV`,
`NOINT`) and subscreen IDs (`3010` through `3040`).
Constants include main/modal window indexes, `&XXL` export, export menu-code
candidates, `&MB_EXPORT`, and the layout-name column `VARIANT`.

```python
from resin.gui import GUI

assert GUI.execute_txn_btn() == "wnd[0]/tbar[1]/btn[8]"
assert GUI.export_dialog_dirpath() == "wnd[1]/usr/ctxtDY_PATH"
stem = GUI.SapFieldIdStem.parse("wnd[0]/usr/ctxtBWART-LOW")
assert stem.base == "BWART" and stem.variant == "LOW"
assert stem.compile() == "ctxtBWART-LOW"
assert GUI.SapFieldIdStem.selection_button("BWART") == "btn%_BWART_%_APP_%-VALU_PUSH"
```

`SapFieldIdStem` is frozen/slotted and parses the last segment of a full ID
or a standalone stem. It supports lowercase component type, uppercase
base/variant identifiers, selection-button bodies, a container index, or
two grid coordinates. Coordinates must appear together and cannot coexist
with a container index. `compile()` returns only the stem.
It is not a parser for every possible SAP component ID.
`ctxt_cell_id` builds coordinates with a space (`[1, 0]`), whereas the stem
parser currently accepts unspaced coordinates (`[1,0]`); these two utilities
do not directly round-trip.

`txn_variant_fields` and `after_window` exist in the defining `builders` and
`parts` modules respectively, but are omitted from those modules' `__all__`
and are not available through `GUI`.

## Additional current caveats

* `resin.utils.runtime.poll_until` currently treats **any normal return**,
  including `None`/`False`, as success; only exceptions trigger retries.
  Thus `session.wait_for_component(..., _raise=False)` may return `None`
  immediately on a missing component. Its `_raise=True` form retries missing
  lookup exceptions. The standalone
  `resin.gui.utils.wait_for_component(..., _raise=True)` still invokes
  `session.find(..., _raise=False)`, so it can return `None` immediately too.
  Explicitly inspect results rather than assuming the configured timeout
  implies a wait.
* `GridView.find_row`/`find_rows` pass `ignore_case` positionally to a
  keyword-only `_get_cell_value` parameter, causing `TypeError` when rows
  are inspected. Reverse lookup also starts at `RowCount` and excludes row
  zero. Do not rely on these helpers for layout selection without addressing
  those limitations.
* `Statusbar` inherits `Component`, not `VComponent`, and has no `text`
  property. Its formatted `status` currently shows `"<unknown>"` for text.
  `Session.raise_on_error()` reads raw COM `Text` and is separate from this
  diagnostic formatting.
* Transaction export can have process-cleanup side effects: the coordinating
  transaction service calls `fs.kill_process_by_open_file` with
  `by_filename=True`. Do not run `Transaction.export()`/exporting pool jobs
  as a supposedly read-only probe on a shared desktop. Direct export-service
  use is a separate workflow; review the export guide's safety constraints.

These limitations are documented, not silently repaired by configuration.

## Public import surface

Use named imports rather than depending on incidental names introduced by
wildcard imports:

* `resin.gui`: `Application`, `Connection`, `Session`, `ComGateway`,
  `SapContext`, `AppManager`, SAP exceptions, re-exported model/component/pool
  names, `GUI`, and `debug_component`.
* Service aliases `ExportService`, `TransactionService`, and
  `SessionPoolService` are **modules**, not service instances.
  `Transaction` and `build_result_dict` are also exported from `resin.gui`.
  Export service symbols are separately re-exported there.
  *TODO: rename or remove Service aliases*
* `resin.gui.core`: includes `SessionInfo` in addition to the three core
  wrappers. `SessionInfo` is not directly re-exported from `resin.gui`.
* `resin.gui.models`: connection, transaction, and export DTOs/enums above,
  together with their `*Dict` configuration types.
* `resin.gui.components`: `Component`, `VComponent`, `Container`,
  `VContainer`, `UserArea`, `CheckBox`, `RadioButton`, `TextField`,
  `CTextField`, `Label`, `Button`, `Tab`, `GridView`, `Shell`, `Statusbar`,
  `StatusMessageType`, `TableControl`, and window classes; `registry` is a
  module. Import `TabStrip` and factory helpers from their defining modules.
* `resin.gui.services.pool` (also re-exported by `resin.gui`):
  `SessionPool`, `SessionPoolOptions`, `SessionPoolOptionsDict`,
  `SessionProvisioner`, `SessionProvisionerOptions`,
  `SessionProvisionerOptionsDict`, `SessionProvisioningResult`,
  `SessionLocator`, `SessionBinding`, `ConnectionLocator`, `ConnectionLease`,
  `SessionPoolError`, discovery/provision/launcher helpers, and protocols
  `SapGuiLauncher`, `ConnectionBootstrapper`, `ApplicationFactory`, plus
  `PendingCommand`. Import worker/command/assignment classes directly from
  their modules.
* `resin.gui.utils`: `busy_safe`, legacy idle/concurrency helpers,
  `debug_component`, standalone `wait_for_component`, `gui_id`, and
  runtime-checkable `HasSession`, `SupportsSet`, `SupportsPress`,
  `SupportsSelect` protocols. `FindMixin`/`SupportsFind` live in
  `resin.gui.utils.mixin`; COM lifetime/polling helpers live in
  `resin.utils.runtime`.

The SAP exception hierarchy is rooted at `SapGuiError`: availability, COM,
connection/session/component-not-found, invalid-context, and status errors.
`SapComError` also derives from resin's general `ComError`.
`SessionPoolError` is a separate `RuntimeError` subclass.

## Source and validation coverage

This guide was checked against **69 Python modules**, the complete GUI source
scope excluding the 12 modules in `services\_export` and five in
`services\transaction`. Coverage: GUI root (4), COM (4), core (5), components
(11), models including transaction/export DTOs (16), pool (15),
`services\__init__` (1), and utilities including GUI IDs (13).
The shared `resin.utils.runtime` implementation was also inspected.

Python examples passed Python 3.11 syntax validation. Pure configuration,
enum/ID parsing, public-import checks, and the noted polling/default
differences were checked with resin's `.venv\Scripts\python.exe` (3.11.3),
with live COM attachment/dispatch blocked. Connection creation/capacity
polling is covered by four focused mocked-COM regression tests in
`tests\test_gui_connection.py`. These checks did not exercise live SAP,
Excel, authentication, or actual file export.
