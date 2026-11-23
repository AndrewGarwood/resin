# resin

## Documentation

See the [documentation index](docs/README.md) for GUI sessions and pooling,
transactions and exports, SAP save-dialog debugging, AO/IBP controllers,
and shared utilities.

## Transaction field definitions

Transaction fields are unresolved configuration definitions. Construction and
`Transaction.set_field()` copy definitions without evaluating them. Immediately
before loading each screen, resin resolves and validates that screen
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
includes the radio option. Use either `"RADIO_BUTTON_SELECT"` or
`{"sentinel": "RADIO_BUTTON_SELECT"}`.

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
Provide include/exclude definitions rather than relying on the marker alone. Empty lists,
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
uses the actual scrollbar position after scrolling. Single values use clipboard
paste by default; pass `copy_to_clipboard=None` to `Transaction` for row-by-row
entry. Unavailable rows, unexpected
windows, and failures to return to the original window raise errors rather than
silently dropping selections. No temporary selection files are used.

Custom selection dialogs are not supported. These multi-selection dialog IDs and behaviors are
covered by mock-based tests, **not live multi-selection SAPGUI verification**. Verify them in your
SAP system before production use, especially Delete All, table expansion across
pages, and selection validation on confirmation. Failures leave the dialog open
for inspection; there is no automatic cancellation or rollback.

A preparation error causes no configured field writes on the affected screen.
This is not rollback: navigation, variant loading, previous screens, and writes
made before a subsequent SAPGUI/COM error may already have occurred. Field errors
preserve their exception causes and use cached status rather than querying SAPGUI
again while handling a failure.

Two existing validation test cases currently disagree with runtime behavior:
an action-only multiple-selection object clears selections, and a radio action
object with extra keys is accepted. Use the explicit forms above; these
discrepancies are not addressed by the export-dialog investigation.

Run the tests in an environment with the project installed:

```powershell
python -m unittest discover -s tests -v
```