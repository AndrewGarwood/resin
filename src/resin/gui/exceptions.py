"""
*`@file`* `resin/gui/exceptions`
"""
from __future__ import annotations


class SapGuiError(RuntimeError):
    """Base exception for SAP GUI wrapper failures."""


class SapGuiNotAvailableError(SapGuiError):
    """SAP GUI or its scripting engine is unavailable."""


class SapComError(SapGuiError):
    """A COM call failed or returned an incompatible object."""


class SapConnectionNotFoundError(SapGuiError):
    """A requested SAP GUI connection could not be found."""


class SapSessionNotFoundError(SapGuiError):
    """A requested SAP GUI session could not be found."""


class SapComponentNotFoundError(SapGuiError):
    """A requested SAP GUI component could not be found."""


class SapInvalidContextError(SapGuiError):
    """A wrapper does not contain the IDs required for an operation."""


class SapGuiStatusError(SapGuiError):
    def __init__(
        self,
        *,
        text: str,
        message_id: str,
        message_number: str,
        session_id: str,
    ) -> None:
        self.text = text
        self.message_id = message_id
        self.message_number = message_number
        self.session_id = session_id

        super().__init__(
            f"SAP error [{message_id} {message_number}] "
            f"in session {session_id!r}: {text}"
        )