"""
*`@file`* `gui/services/pool/provisioner`


```
provisioner = SessionProvisioner(
    SessionProvisionerOptions(
        session_count=3,
        connection_description="Production System",
        launch_if_unavailable=True,
        close_created_sessions_on_exit=True,
        close_bootstrap_session_on_exit=False,
    ),
    launcher=launch_sap_gui,
)

pool, provisioning = SessionPool.provisioned(
    provisioner
)

with pool:
    results = pool.run(transactions)
```

"""
from __future__ import annotations
from collections.abc import Callable

from pyqi import (export)
from lute import LogMsg, get_logger

from resin.gui.com import runtime
from resin.gui.com.gateway import ComGateway
from resin.gui.core.application import Application
from resin.gui.core.connection import Connection
from resin.gui.core.session import Session
from resin.gui.exceptions import (
    SapConnectionNotFoundError,
    SapGuiNotAvailableError,
)
from resin.gui.services.pool.connection import ConnectionLease, ConnectionLocator
from .provisioner_types import (
    SessionProvisionerOptions, 
    SessionProvisioningResult,
)
from .session_binding import (SessionBinding)
from .session_locator import (SessionLocator)
from .types import (ConnectionBootstrapper, SapGuiLauncher)

mlog = get_logger(__file__)


class SessionProvisioner:
    """
    Resolves or creates the SAP GUI sessions required by a SessionPool.

    The provisioner is intentionally short-lived. It performs its work inside
    one temporary COM apartment and returns immutable SessionBinding objects.

    It does not retain Application, Connection, Session, or raw COM dispatch
    objects after provision() returns.
    """

    def __init__(
        self,
        options: SessionProvisionerOptions,
        /,
        *,
        gateway_factory: Callable[[], ComGateway] = ComGateway,
        launcher: SapGuiLauncher | None = None,
        connection_bootstrapper: ConnectionBootstrapper | None = None
    ):
        """
        - *`@param`* `launcher (SapGuiLauncher | None)` 
            - callable that launches the SAPGUI executable
        - *`@param`* `connection_bootstrapper (ConnectionBootstrapper | None)` 
            - callable that creates a `Connection` from an `Application` instance       
        """
        self.options = options
        self._gateway_factory = gateway_factory
        self._launcher = launcher
        self._connection_bootstrapper = connection_bootstrapper

    
    def provision(self) -> SessionProvisioningResult:
        """
        Return bindings for exactly options.session_count sessions.

        Existing sessions are borrowed. Sessions created by this invocation
        receive the configured close-on-exit policy.
        """
        with runtime.com_apartment():
            return self._provision_in_com_apartment()

    def _provision_in_com_apartment(self) -> SessionProvisioningResult:
        application, launched_application = (
            self._attach_application()
        )

        connection, opened_connection = (
            self._resolve_connection(application)
        )
        connection_owned = (
            opened_connection
            and self.options.close_opened_connection_on_exit
        )
        existing_sessions = list(connection.sessions)

        if not existing_sessions:
            raise RuntimeError(
                "The selected SAP connection has no sessions. "
                "Connection.create_session() requires an existing "
                "source session."
            )

        requested_count = self.options.session_count

        selected_existing = existing_sessions[:requested_count]
        bindings = [
            self._binding_for_session(
                application,
                connection,
                session,
                close_on_exit=False,
            )
            for session in selected_existing
        ]

        created_count = 0

        while len(bindings) < requested_count:
            source_session = self._select_source_session(
                connection,
                bindings,
            )

            created_session = connection.create_session(
                source_session=source_session,
                timeout=self.options.create_timeout,
                poll_interval=self.options.create_poll_interval,
            )

            bindings.append(
                self._binding_for_session(
                    application,
                    connection,
                    created_session,
                    close_on_exit=self.options.close_created_sessions_on_exit,
                )
            )

            created_count += 1

        bindings = self._normalize_session_ownership(
            bindings,
            connection_owned=connection_owned,
        )

        self._validate_result(bindings)

        return SessionProvisioningResult(
            bindings=tuple(bindings),
            connection=ConnectionLease(
                ConnectionLocator(
                    application_id=application.id,
                    connection_id=connection.id
                ),
                close_on_exit=connection_owned
            ),
            reused_session_count=(
                len(bindings) - created_count
            ),
            created_session_count=created_count,
            launched_application=launched_application,
        )

    # ========================================================================
    # Application bootstrap
    # ========================================================================
    def _attach_application(
        self,
    ) -> tuple[Application, bool]:
        """ 
        *`@returns`* `Application, created_by_launcher`
        """
        try:
            return self._create_application(), False
        except SapGuiNotAvailableError:
            if not self.options.launch_if_unavailable:
                raise
            if self._launcher is None:
                raise RuntimeError(
                    "SAP GUI is unavailable and "
                    "launch_if_unavailable=True, but no launcher "
                    "was provided"
                )
        self._launcher()
        return (runtime.poll_until(
            self._create_application, 
            timeout=self.options.attach_timeout, 
            poll_interval=self.options.attach_poll_interval,
            description="SessionProvisioner._attach_application() → Application"
        ), True)

    def _create_application(self) -> Application:
        gateway = self._gateway_factory()
        return Application.attach(gateway)
    
    # ========================================================================
    # Connection bootstrap
    # ========================================================================

    def _resolve_connection(self, application: Application, /) -> tuple[Connection, bool]:
        """ 
        *`@returns`* `Connection, opened_by_provisioner`

        Tries to find/return existing connection, else see if application has one that matches:
        1. `connection.id`
        2. `connection.description`
        3. `connection.string`

        """
        existing = self._find_existing_connection(application)
        if existing is not None:
            return existing, False
        if self._connection_bootstrapper is not None:
            connection = self._connection_bootstrapper(application)
            self._validate_connection(connection)
            return connection, True
        if self.options.connection.description is not None:
            return (
                application.open_connection(
                    self.options.connection.description,
                ),
                True,
            )
        if self.options.connection.string is not None:
            return (
                application.open_connection_by_string(
                    self.options.connection.string,
                ),
                True,
            )
        raise SapConnectionNotFoundError(LogMsg(
            f"Failed to obtain SAPGUI Connection.",
            f"No existing SAP connection found and no connection matched",
            f"selectors in self.options:",
            options=str(self.options.connection)
        ))
    
    def _find_existing_connection(
        self,
        application: Application,
        /,
    ) -> Connection | None:
        """
        searches w/ self.options.connection props in following order (if defined):
        1. `connection.id`
        2. `connection.description`
        3. `connection.string`
        4. `connection.index`
        """
        options = self.options

        if options.connection.id is not None:
            return application.find_connection(
                connection_id=options.connection.id,
            )

        if options.connection.description is not None:
            connection = application.find_connection(
                description=options.connection.description
            )
            # connection = application.open_connection(
            #     options.connection.description, 
            #     raise_on_error=False
            # )
            if connection is not None:
                return connection
        if options.connection.string is not None:
            connection = application.find_connection(
                connection_string=options.connection.string,
            )
            if connection is not None:
                return connection
        if (options.connection.index is None):
            raise RuntimeError(LogMsg(
                f"Invalid SessionProvisionerOptions",
                f"Unable to select/identify a target Connection",
                options=options.__str__(),
                conn_options=str(options.connection)
            ))
        try: return application.connections[options.connection.index]
        except IndexError: return None
    
    @staticmethod
    def _validate_connection(
        connection: Connection,
        /,
    ) -> None:
        """
        try reading `id` and `session_count`. should be called within Provisioner's `com_apartment`
        """
        # Force a COM-backed read while still in the provisioner's
        # COM apartment.
        _ = connection.id
        _ = connection.session_count

    # ========================================================================
    # Sessions and bindings
    # ========================================================================

    @staticmethod
    def _normalize_session_ownership(
        bindings: list[SessionBinding],
        /,
        *,
        connection_owned: bool,
    ) -> list[SessionBinding]:
        if not connection_owned:
            return bindings

        # Connection.close() owns cleanup for every session under it.
        return [
            SessionBinding(
                locator=binding.locator,
                close_on_exit=False,
            )
            for binding in bindings
        ]

    @staticmethod
    def _binding_for_session(
        application: Application,
        connection: Connection,
        session: Session,
        /,
        *,
        close_on_exit: bool,
    ) -> SessionBinding:
        if session.connection_id != connection.id:
            raise RuntimeError(
                "Provisioned session belongs to an unexpected "
                "SAP connection: "
                f"expected={connection.id!r}, "
                f"received={session.connection_id!r}"
            )

        return SessionBinding(
            locator=SessionLocator(
                application_id=application.id,
                connection_id=connection.id,
                session_id=session.id,
            ),
            close_on_exit=close_on_exit,
        )

    @staticmethod
    def _select_source_session(
        connection: Connection,
        bindings: list[SessionBinding],
        /,
    ) -> Session:
        """
        Resolve one currently live selected session as the source for
        Connection.create_session().
        """
        if not bindings:
            raise RuntimeError(
                "Cannot create another SAP session without a "
                "bootstrap session"
            )

        # Prefer the first selected session for deterministic behavior.
        source_id = bindings[0].locator.session_id

        return connection.require_session(source_id)

    # def _apply_bootstrap_ownership(
    #     self,
    #     bindings: list[SessionBinding],
    #     /,
    #     *,
    #     connection_was_opened: bool,
    # ) -> list[SessionBinding]:
    #     """
    #     Optionally mark the first selected session as pool-owned.

    #     By default the bootstrap session is borrowed, even when the
    #     provisioner opened the connection. This preserves one session after
    #     pool shutdown and avoids leaving the next provisioning attempt with
    #     no source session.
    #     """

    #     should_mark_pool_owned = (
    #         bool(bindings) 
    #         and connection_was_opened 
    #         and self.options.close_opened_connection_on_exit
    #     )
    #     if (not should_mark_pool_owned):
    #         return bindings

    #     bootstrap = bindings[0]

    #     bindings[0] = SessionBinding(
    #         locator=bootstrap.locator,
    #         close_on_exit=True,
    #     )

    #     return bindings

    def _validate_result(
        self,
        bindings: list[SessionBinding],
    ) -> None:
        if len(bindings) != self.options.session_count:
            raise RuntimeError(
                "Session provisioning returned an unexpected "
                "number of bindings: "
                f"expected={self.options.session_count}, "
                f"received={len(bindings)}"
            )

        seen: set[tuple[str, str]] = set()

        for binding in bindings:
            key = (
                binding.locator.connection_id,
                binding.locator.session_id,
            )
            if key in seen:
                raise RuntimeError(
                    "Session provisioning produced duplicate "
                    f"binding {key!r}"
                )
            seen.add(key)


__all__ = export(SessionProvisioner)