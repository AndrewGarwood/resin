"""
*`@file`* `gui/services/pool/session_locator`
"""
from dataclasses import dataclass
from pyqi import require
from resin.gui.com.gateway import (ComGateway)
from resin.gui.core.session import (Session)
from resin.gui.context import (SapContext)

@dataclass(frozen=True, slots=True)
class SessionLocator():
    """ 
    - callable, immutable 
    - describes where/how an existing SAP session can be resolved.
    - contains no resolved COM dispatch objects.
    """
    connection_id: str
    session_id: str
    application_id: str | None = None
    def __post_init__(self) -> None:
        require.non_empty_string(
            self.connection_id,
            "connection_id",
        )
        require.non_empty_string(
            self.session_id,
            "session_id",
        )

        if self.application_id is not None:
            require.non_empty_string(
                self.application_id,
                "application_id",
            )
    def resolve(
        self,
        *,
        gateway: ComGateway | None = None,
    ) -> Session:
        return Session(
            gateway=gateway or ComGateway(),
            context=SapContext(
                application_id=self.application_id,
                connection_id=self.connection_id,
                session_id=self.session_id,
            ),
        )

    def __call__(self, *, gateway: ComGateway | None = None) -> Session:
        return self.resolve(gateway=gateway)

__all__ = ['SessionLocator']