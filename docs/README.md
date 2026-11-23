# Resin documentation

Resin automates SAP GUI transactions and SAP Analysis for Office / IBP Excel
workbooks through Windows COM and desktop automation.

## Guides

- [GUI core, components, sessions, and pooling](gui.md)
- [Transaction fields, execution, and exports](transactions.md)
- [SAP versus Windows save dialogs: investigation and live probe](sapgui-save-dialogs.md)
- [Analysis for Office and IBP workbook controllers](workbooks.md)
- [Shared field models, runtime, clipboard, and Windows automation](utilities.md)

These guides describe the current source, including operational limitations;
they do not imply every SAP transaction, dialog, or workbook is supported.

## Environment

The package requires Python 3.11 or newer. Live automation requires Windows,
SAP GUI scripting enabled on both client and server, and, for workbook
controllers, Microsoft Excel with the relevant SAP add-in installed. COM
objects must stay on their owning initialized thread.

Dependencies are `pyqi`, `lute`, `noxl`, `pywin32`, and `pywinauto`.
The checked-in `pyproject.toml` uses editable sibling paths for `pyqi`, `lute`,
and `noxl`; keep that layout when using this development checkout.

From the package root, after installing the project in its environment:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Most tests use mocks and do not certify live SAP/Excel behavior. The
[live export probe](sapgui-save-dialogs.md#running-the-probe) is explicit opt-in
and is not collected by unittest discovery. It runs LX02 in a newly created
session and saves uniquely named workbooks only in the authorized test directory.
Do not run live tests while another person is interacting with the same session.

Use the package's `Result.success`/`Result.error`, controller exceptions, and
documented completion checks rather than assuming that a COM call returning or a
file already existing proves a successful refresh/export.
