"""
*`@file`* `gui/services/pool/exceptions`
"""

class SessionPoolError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        errors: list[tuple[str, BaseException]],
    ) -> None:
        super().__init__(message)
        self.errors = tuple(errors)