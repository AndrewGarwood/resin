"""
*`@file`* `_workbook/exceptions`
"""
from lute import LogMsg
from pyqi import export

class WorkbookControllerError(RuntimeError):
    def __init__(self, message: str | LogMsg, **context: object) -> None:
        self.context = context
        super().__init__(message)

    def add_context(self, **context: object) -> None:
        for key, value in context.items():
            self.context.setdefault(key, value)
        self.add_note(", ".join(f"{key}={value}" for key, value in context.items()))


class ExcelComValueError(WorkbookControllerError):
    """ If API (e.g. ao) returned an Excel error instead of a scalar value."""

class ConfigurationError(WorkbookControllerError, ValueError):
    pass


class ConnectionBindingError(WorkbookControllerError):
    pass


class RefreshTimeoutError(WorkbookControllerError, TimeoutError):
    pass


class WorkbookIOError(WorkbookControllerError):
    pass


class PublicationError(WorkbookIOError):
    pass


class DeadSessionError(WorkbookControllerError):
    pass


__all__ = export(
    WorkbookControllerError, 
    ExcelComValueError, 
    ConfigurationError, 
    ConnectionBindingError, 
    RefreshTimeoutError, 
    WorkbookIOError, 
    PublicationError, 
    DeadSessionError
)

