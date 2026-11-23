# Fields, runtime, and Windows utilities

The utility layers are `resin.models._field` (configuration values),
`resin.utils.runtime` (COM/message pumping/polling), and
`resin.utils.winauto` (pywinauto discovery, ownership checks, controls, watchers,
and diagnostics). `_workbook` adds refresh-specific timestamps and deadlines;
see [workbooks.md](workbooks.md).

These are Windows/COM-oriented modules, not a portable headless automation layer.
Root `resin` eagerly imports GUI/AO/IBP modules, so even a field-only import can
load desktop dependencies. Examples below are syntax-only, not executed.

## Field resolution

Import `from resin.models import _field`; `models.__init__` does not re-export
the field API. `_field.__init__` imports built-in providers as `RegisterSentinels`
and populates the shared `SENTINEL_FUNCTION_REGISTRY`.

```text
resolve_field_value(value, /) -> Any
resolve_field_dict(fields: Mapping[str, Any], /) -> dict[str, Any]
resolve_sentinel_value_dict(value, /, allow_bare_sentinel=True) -> Any
is_sentinel_value_dict(value, /) -> bool
is_reserved_kwarg(value, /) -> bool
```

A provider definition is `{"sentinel": "<SentinelKey>", "args": [...], ...kwargs}`.
`args` defaults to `[]` and must be a **list**. Only `sentinel` and `args` are
reserved; every other entry is a provider keyword argument, not a nested
`kwargs` envelope. Sentinel names must be strings resolving to a `SentinelKey`
member name/value; unknown explicit names raise `ValueError`.

The resolver recursively visits ordinary mappings, lists, tuples, provider
arguments, and provider keyword values. It preserves list/tuple shape and
mapping keys, creating new containers rather than mutating input.
Bare recognized sentinel strings resolve at **all these depths**, not just at the
top level. Unknown ordinary strings remain literal. Provider return values are
returned as-is, not recursively resolved a second time.
`allow_bare_sentinel=False` on `resolve_sentinel_value_dict` suppresses bare-string
resolution recursively, while explicit nested sentinel objects still resolve.
`resolve_field_value`/`resolve_field_dict` do not offer that flag.

`RADIO_BUTTON_SELECT` and `MULTIPLE_SELECTION` are action markers, not value
providers: explicit objects are deep-copied intact, including their payload;
bare action strings remain strings. This module does not perform their actions.
`is_sentinel_value_dict` only tests mapping + string-valued `sentinel`, not whether
the name is recognized or arguments are valid.

Bad sentinel/argument types raise `TypeError`; unknown/unregistered providers
raise `ValueError`. Provider failures become path-labelled `ValueError` with a
cause, e.g. `fields['date'].args[0]`. There is no evaluation cache: every call
can recompute today's date or call a custom provider again.

```python
from resin.models import _field

def resolve_report_fields():
    definition = {
        "period": {
            "sentinel": "CUSTOM_RANGE",
            "lower": {"month_offset": -1, "day": "first"},
            "upper": {"month_offset": -1, "day": "last"},
        },
        "run_date": {
            "sentinel": "CUSTOM_DATE",
            "anchor": "2026-11-23",
            "day_offset": -1,
            "fmt": "%Y-%m-%d",
        },
    }
    return _field.resolve_field_dict(definition)
```

### Built-in sentinel providers

Default `fmt` is `"%m/%d/%Y"` unless noted. Dates are computed through local
`date.today()`/pyqi date helpers; provider results are formatted strings.
The provider functions are available on `_field.RegisterSentinels`.

| `SentinelKey` | Provider signature / semantics |
| --- | --- |
| `CURRENT_DAY` | `current_day(fmt="%m/%d/%Y")`: today |
| `FIRST_DAY_OF_MONTH` | `first_day_of_month_text(anchor=None, fmt="%m/%d/%Y")`: first day of anchor/current month |
| `LAST_DAY_OF_MONTH` | `last_day_of_month_text(anchor=None, fmt="%m/%d/%Y")`: last day of anchor/current month |
| `FIRST_DAY_OF_YEAR` | `first_day_of_year_text(year=None, fmt="%m/%d/%Y")`: January 1; falsy year uses current year |
| `LAST_DAY_OF_YEAR` | `last_day_of_year_text(year=None, fmt="%m/%d/%Y")`: December 31 |
| `ROLLING_YEAR_LOWER` | `rolling_year_lower_text(fmt="%m/%d/%Y")`: last day of current month last year |
| `ROLLING_YEAR_UPPER` | `rolling_year_upper_text(fmt="%m/%d/%Y")`: last day of current month this year |
| `ROLLING_12M_LOWER` | `rolling_12m_lower(fmt="%m/%d/%Y")`: first day of current month last year |
| `ROLLING_12M_UPPER` | `rolling_12m_upper(fmt="%m/%d/%Y")`: last day of current month this year |
| `PREVIOUS_BUSINESS_DAY` | `previous_business_day(fmt="%m/%d/%Y", holidays=None)`: previous Monday-Friday excluding supplied holidays |
| `CUSTOM_DATE` | `custom_date(*, fmt="%m/%d/%Y", **kwargs)`: forwarded date computation |
| `CUSTOM_RANGE` | `custom_range(*, lower, upper, leftpad=2, fmt="%m/%Y")`: formatted `"lower - upper"` |

Month-provider string anchors are parsed with the same `fmt` used for output.
`PREVIOUS_BUSINESS_DAY` accepts a collection of holiday strings; it offers no
reference-date argument. `CUSTOM_DATE` is the actual key, **not** `COMPUTE_DATE`.
Its forwarded pyqi arguments are `anchor=None`, `year_offset=0`,
`month_offset=0`, `day_offset=0`, `year=None`, `month=None`, `day=None`.
An anchor defaults to today; offsets apply before explicit year/month/day
overrides. Month may be an integer or full month name; day may be an integer,
`"first"`, or `"last"`.

`CUSTOM_RANGE.lower`/`.upper` must be date-computation dictionaries, not
preformatted dates. It computes both bounds, formats them, finds the first
non-alphanumeric/non-`%` separator in `fmt`, splits each result at that separator,
and left-pads the first part to `leftpad`. Use simple two-part formats such as
the default month/year; arbitrary strftime layouts are not a general range API.
Missing separators raise `ValueError`; bounds are not checked for ordering.

The registry is a `pyqi.Registry(SentinelKey, normalize_key=SentinelKey.resolve)`.
Use `.register(key, *, replace=False)` as a decorator and `.call(key, /, *args,
**kwargs)` for direct calls. Duplicate registrations fail unless `replace=True`;
provider exceptions are wrapped by pyqi before field resolution wraps them.
Replacing a provider changes process-global behavior. The resolver still accepts
only enum keys and still preserves action markers; registering an arbitrary new
string/action handler does not automatically extend field resolution.

### Ranges and selection models

These dataclasses describe include/exclude selections; they neither fill a UI
nor issue AO commands:

```text
ValueRange(lower, upper)
ValueRange.from_dict(data, /, *, resolve=True)
MultiSelection(values=[], ranges=[])  # fresh lists per instance
MultiSelection.from_dict(data, /, *, resolve=False)
ValueOptions(include=None, exclude=None)
ValueOptions.from_dict(data, /, *, resolve=False)
ValueOptions.from_sequence(values: list | tuple, /, *, resolve=True)
```

`ValueRange.from_dict` requires exactly `{"lower", "upper"}`. Bounds are resolved
when requested, then rejected if `None`, mappings, sets, non-string sequences,
or lacking `SupportsComparison`. It does not compare lower to upper.
Direct `ValueRange` construction bypasses that validation.

`MultiSelection` accepts `{"values": [...], "ranges": [{"lower": ..., "upper": ...}]}`.
The normal dictionary path obeys `resolve`; its legacy list input classifies exact
range dictionaries and always uses resolving `ValueRange.from_dict` for them,
but leaves single values unresolved.

`ValueOptions` accepts `{"include": <selection>, "exclude": <selection>}`.
`from_dict` also supports an include list or legacy top-level `values` list;
that list shortcut stays unresolved even with `resolve=True`.
`from_sequence` is the consistent list/tuple classifier: ranges go to
`include.ranges`, other entries to `include.values`, and its default resolves both.
Use `resolve=True` for deferred definitions and false for already evaluated ones;
dictionary defaults are false. Constructors wrap parsing failures as `RuntimeError`;
`from_sequence` rejects non-list/tuple input directly with `TypeError`.

`is_value_range_dict`, `is_multi_selection_dict`, and `is_value_options_dict`
are shape checks, not bound evaluation. They accept only `dict`; range keys must
be exact, selection keys limited to `values`/`ranges` with lists, and options must
be nonempty with only `include`/`exclude` keys. The permissive constructor shortcuts
are broader than these strict guards.

## COM runtime, polling, and timestamp helpers

`runtime.com_apartment()` balances `pythoncom.CoInitialize()` and
`CoUninitialize()` on the **current thread**. Every worker using COM needs its own
apartment; never share un-marshalled Excel proxies across threads.
`pump_waiting_messages()` requires an already initialized apartment and wraps
pump failures as `resin.utils.ComError`. `try_pump_waiting_messages()` logs failure
and returns `False`, otherwise `True`.

```text
validate_polling(timeout, poll_interval) -> tuple[float, float]
poll_until(operation, *, timeout, poll_interval, description,
           retry_on=(Exception,), _raise=True) -> Any
```

Validation requires positive timeout/interval and returns floats. `poll_until`
retries exceptions in `retry_on`, pumps best-effort, and sleeps within a monotonic
budget. Exhaustion raises `TimeoutError` (chained from the last retry error), or
logs and returns `None` with `_raise=False`; other exceptions propagate.
**Current caveat:** its private `_MISSING` marker is never exposed to callers,
so *any normal return*, including `None`, `False`, or `0`, terminates polling
immediately. Signal "not ready" by raising a selected retry exception, not by
returning `None`. Calls themselves are not interrupted by the timeout.

Refresh-specific helpers exported via `_workbook`/root:

* `is_excel_error_value(value, /)` recognizes non-bool integers strictly between
  `-2146827000` and `-2146826000`.
* `parse_refresh_timestamp(value, /, *, require_null_tzinfo=True,
  use_1904_epoch=False)` returns a datetime or `None`. `None`, `""`, and numeric
  zero are absent; datetimes must be unzoned by default. Numeric strings may have
  leading `=` and outer quotes; negative/non-numeric literals and unsupported
  types fail validation. Numeric values are Excel serial days using pyqi's
  1900/1904 epoch helper, not Unix timestamps. ISO timestamp strings are rejected;
  disabling the timezone check does not normalize a datetime's zone.
* `Deadline` and `cooldown_remaining` are documented in workbooks.md.

AO's `require_ao_bool(value, /, label)` accepts bool/numeric zero-or-one, rejecting
Excel errors as `ExcelComValueError` and other values as `AoCommandError`.
`to_error_tuple(value, /)` unwraps singleton lists/tuples, returns `(None, None)`
for empty/absent data, stringifies the first two sequence items, or treats a scalar
as the code. `error_is_clear(value, /)` accepts code `None`, `""`, `"0"`, `"0.0"`
with message `None`, `""`, `"None"`. `is_busy(error)` recognizes AO busy HRESULTs.

## Window discovery and ownership

The `winauto` facade exposes `window`, `control`, `application`,
`DesktopBackend.UIA/WIN32` (`"uia"`/`"win32"`), and these aliases:

```text
connect_application(pid, /, *, backend=None, handle=None, path=None,
                    timeout_seconds=30.0) -> Application
find_window(criteria, /, *, app=None, backend=None, require_unique=True,
            strict=True, selector=None, expected_wrapper=None)
find_window_by_spec(spec, /, *, backend=None, strict=True, timeout=10.0,
                    retry_interval=1.0, expected_wrapper=BaseWrapper)
attach_process_to_window(pid, criteria, /, *, backend=None,
                         require_unique=True, timeout_seconds=30.0)
    -> (Application, BaseWrapper)
```

Application connection attaches by PID (optional handle/path constraints),
without ownership of shutdown. A missing backend there uses
`get_backend_name()` from pywinauto; window functions pass their backend directly
to `Desktop`. Specify `"uia"` for IBP ribbon controls; Win32 dialogs often need
`"win32"`.

`WindowCriteria` is an exact-title string, regex `Pattern`, positive integer
handle, or `WindowOptionsDict`. Dictionary entries include `title`, `title_re`,
`class_name`, `class_name_re`, `top_level_only`, `visible_only`, `enabled_only`,
`active_only`, `handle`, `parent`, and `process`. The resolver rejects empty
criteria but forwards dictionaries without entry validation; regex flags are
not forwarded, only `.pattern`. `window.utils.resolve_window_specification`
also accepts an existing `WindowSpecification`.

`find_window` enumerates current windows, not a timed readiness wait.
One candidate wins; multiple candidates use a supplied selector, otherwise
uniqueness is enforced or the first candidate is returned. Strict lookup failures
raise `AutomationError`; non-strict enumeration/selection failures return `None`.
Invalid criteria can fail before that suppression. A wrong `expected_wrapper`
always raises, even with `strict=False`.

`find_window_by_spec` waits only for `.exists`, then gets `.wrapper_object()`;
it does not wait for visible/enabled/ready. Non-strict absence returns `None`,
but other errors, including wrapper mismatch, are still wrapped as
`AutomationError`. Timeout/retry interval must be positive.

Scope every desktop action to the intended PID/handle; a title alone is not
proof of ownership. Native helpers are independent checks, not automatically
applied by find functions:

* `iter_owner_chain(hwnd)` yields the window itself, then each `GW_OWNER`.
* `is_owned_by(hwnd, expected_owner_hwnd)` checks membership in that chain.
* `window_process_id(hwnd)` returns the native PID.
* `is_candidate_dialog(hwnd, *, expected_owner_hwnd, expected_process_id)` applies
  every non-`None` constraint; with both `None` it accepts any candidate.
  These are native **owner** relationships, not parent/child containment.

### Controls, states, legacy helpers, and diagnostics

`generate_control_key(ctrl, /)` returns stringified control type, handle,
automation ID, and rectangle; it is a snapshot/deduplication key, not a durable
selector. `control_is_available(ctrl, /)` checks truthiness, visibility, and
enabled state. `CommonControl`, `UiaControl`, and `Win32Control` name backend
control types; `Win32Window.DIALOG="#32770"` and `.POPUP="#32768"`.

`WindowState` has `exists`, `visible`, `enabled`, `ready`, `active`.
`all_of(*states)` joins states with spaces and rejects no arguments;
cached `available()` returns `"exists ready"`. Deprecated `ControlState` offers
`"exists ready"`/`"visible enabled"`.
Deprecated `ControlOptions(class_name=None, title_re=None, title=None,
visible_only=None)` defaults visibility to true, joins pattern/title collections
as regex alternatives without escaping, and raises if `.class_name` is unset.
Prefer criteria dictionaries.

Under `winauto.window`, legacy
`find_available_control(window, /, title, ctrl_types, require_unique=True)` searches
descendants and deduplicates visible/enabled controls.
`find_window_by_title(app, title, /, require_unique=True, ignore_case=True,
window_ctrl_type="Window")` searches title substrings; both wrap failures in
`RuntimeError`. Prefer the explicit modern find functions for new code.

Class helpers are desktop-wide, not PID-scoped:
`get_class(*, backend=None, class_name, visible_only)` returns wrappers;
`class_exists` takes the same arguments;
`wait_for_class(*, backend=None, class_name, visible_only=True, timeout=2.0,
poll=0.05, selector=None)` returns the first/selected item or `None` on exhaustion,
with positive timing validation and ordinary sleep (no message pump).
`dump_class(*, backend=None, class_name, visible_only=True)` logs matches.

Diagnostics: `inspect_descendants(item, /, *, visible_only=True)` logs descendants;
`element_info(el, /)` returns repr-style strings for text/class/handle/visibility/
enabled values (not raw values, and no rectangle despite its TypedDict field);
`dump_owner_chain(hwnd, /)` logs native owners; `describe_window(hwnd)` returns
title/class/owner chain/PID/visibility/enabled data.
Avoid publishing these dumps if window titles or controls contain sensitive data.

## Watchers and clipboard

`NativeDialogWatcher` is an abstract dataclass: required constructor entries are
`cancel`, `done`, `handled_event` (`threading.Event`), and `thread`; defaults are
`handled=False`, `timed_out=False`, `error=None`, `backend=None`.
It supplies state, not an automatically started worker.
Subclass `handle_dialog(dlg, options, *args, **kwargs)` and arrange worker lifecycle:
`mark_handled()` sets state/handled event; `stop()` sets cancellation.
`wait_done(timeout=None)` returns completion state; `wait(timeout=None)` waits for
done and returns handled state. `wait_handled(timeout=None)` also waits for
**done**, not `handled_event`, then raises `RuntimeError` if a worker error exists,
otherwise returns handled. A timeout returns false; `timed_out` is not set for you.

`ibp.warning_watcher.version_warning_watcher(options, /)` starts a daemon worker
with its own COM apartment only during Connect, finds native `DialogWrapper`
warnings, closes them, and marks handled. Missing warnings are normal.
It polls every `0.15` seconds and cancels/joins for `2.0` seconds on exit;
worker failure or failure to stop raises `RuntimeError` if no primary exception
is already propagating. Its own search does not independently verify native
ownership: supply process/handle criteria, particularly because the controller's
automatic PID assignment is currently in an uncalled `__post_init__`.

`resin.utils.default_copy_to_clipboard(payload: str, /)` sends `payload.strip()`
through subprocess stdin to `clip` on `"win32"` or `pbcopy` on `"darwin"`;
`SUPPORTED_PLATFORMS` lists those two names. It replaces the user's clipboard,
removes leading/trailing whitespace, and does not check the subprocess return
code. Other platforms raise `NotImplementedError`; subprocess failures propagate.
The clipboard helper's platform support does not make the overall package portable.

All APIs/defaults above were checked against source. Python examples were parsed
without importing resin or invoking COM, SAP, window search, or clipboard commands;
live Windows/SAP behavior and installed dependency compatibility remain unverified.
