"""
*`@file`* `resin/gui/com/gateway`
- GetObject("SAPGUI"), connection/session resolution, and COM validation.
"""

from __future__ import annotations
from pathlib import Path
import win32com.client as win32
from pyqi.fs import launch_executable
from lute import (LogMsg, annotate, get_logger)
from ..config import (AppManager, SAPGUI_OBJECT_ID)

from ..exceptions import (
    SapComError, 
    SapComponentNotFoundError, 
    SapConnectionNotFoundError, 
    SapGuiNotAvailableError, 
    SapSessionNotFoundError
)
from .types import (DispatchLike)

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Generator, cast

import pythoncom

from ..exceptions import (
    SapComponentNotFoundError,
    SapComError,
    SapConnectionNotFoundError,
    SapGuiNotAvailableError,
    SapSessionNotFoundError,
)
from .types import DispatchLike


mlog = get_logger(Path(__file__).stem)


class ComGateway:
    """
    Boundary between the wrapper model and SAP GUI's COM API.

    The gateway deliberately resolves connections, sessions, and components
    from stable IDs instead of storing long-lived child dispatch objects.

    Threading:
        The calling thread must have an initialized COM apartment. Use
        ``ComGateway.com_apartment()`` at the worker-thread entry point.

    COM ownership:
        Do not share resolved dispatch objects between threads. Wrapper objects
        may be shared only when each operation re-resolves the dispatch object
        on the calling thread and access is otherwise synchronized.
    """

    SAPGUI_PROG_ID = "SAPGUI"

    def __init__(
        self,
        *,
        prog_id: str = SAPGUI_PROG_ID,
        logger: logging.Logger | None = None,
    ) -> None:
        if not isinstance(prog_id, str) or not prog_id.strip():
            raise ValueError("prog_id must be a non-empty string")

        self._prog_id = prog_id
        self._logger = logger or mlog

    @staticmethod
    def com_apartment() -> Generator[None]:
        """
        Initialize COM for the current thread.
        Use this once around the lifetime of a worker thread:
        ```
            with ComGateway.com_apartment():
                run_sap_work()
        ```
        `CoInitialize` and `CoUninitialize` are balanced even when an
        exception occurs.
        """
        pythoncom.CoInitialize()
        try:
            yield
        finally:
            pythoncom.CoUninitialize()

    def get_application(self) -> DispatchLike:
        """
        Return SAP GUI's scripting engine.

        Raises:
            SapGuiNotAvailableError:
                SAP GUI is unavailable or scripting is disabled.
            SapComError:
                SAP returned an incompatible scripting-engine object.
        """
        try:
            sap_gui = win32.GetObject(self._prog_id)
        except Exception as e:
            raise SapGuiNotAvailableError(
                f"Unable to attach to COM object {self._prog_id!r}. "
                "Confirm that SAP GUI is running and SAP GUI scripting is "
                "enabled."
            ) from e

        if sap_gui is None:
            raise SapGuiNotAvailableError(
                f"GetObject({self._prog_id!r}) returned None"
            )

        try:
            application = sap_gui.GetScriptingEngine
        except Exception as e:
            raise SapGuiNotAvailableError(
                "SAP GUI was found, but its scripting engine could not be "
                "obtained. SAP GUI scripting may be disabled."
            ) from e

        return self._require_dispatch(
            application,
            source="SAPGUI.GetScriptingEngine",
            expected_type="GuiApplication",
        )

    def get_connection(self, connection_id: str) -> DispatchLike:
        """
        Resolve an open SAP GUI connection by its runtime ID.

        Example runtime ID:
            /app/con[0]
        """
        self._validate_id(connection_id, name="connection_id")

        application = self.get_application()

        try:
            if (not hasattr(application, "Children")):
                raise SapComError()
            children = application.Children
            count = int(children.Count)
        except Exception as e:
            raise SapComError(
                "Unable to enumerate SAP GUI application connections"
            ) from e

        for index in range(count):
            try:
                candidate = children(index)
            except Exception as e:
                raise SapComError(
                    f"Unable to read application child at index {index}"
                ) from e

            candidate = self._require_dispatch(
                candidate,
                source=f"GuiApplication.Children({index})",
            )

            candidate_id = self._get_string_property(
                candidate,
                "Id",
                source=f"GuiApplication.Children({index})",
            )

            if candidate_id == connection_id:
                candidate_type = self._get_optional_string_property(
                    candidate,
                    "Type",
                )

                if (
                    candidate_type is not None
                    and candidate_type != "GuiConnection"
                ):
                    raise SapComError(
                        f"Object {connection_id!r} was expected to be a "
                        f"GuiConnection but reported type "
                        f"{candidate_type!r}"
                    )

                return candidate

        raise SapConnectionNotFoundError(
            f"SAP GUI connection not found: {connection_id!r}"
        )

    def get_session(
        self,
        connection_id: str,
        session_id: str,
    ) -> DispatchLike:
        """
        Resolve an open SAP GUI session by connection and session IDs.

        Example IDs:
            connection_id = /app/con[0]
            session_id = /app/con[0]/ses[0]
        """
        self._validate_id(connection_id, name="connection_id")
        self._validate_id(session_id, name="session_id")

        connection = self.get_connection(connection_id)

        try:
            children = connection.Children
            count = int(children.Count)
        except Exception as e:
            raise SapComError(
                f"Unable to enumerate sessions for connection "
                f"{connection_id!r}"
            ) from e

        for index in range(count):
            try:
                candidate = children(index)
            except Exception as e:
                raise SapComError(
                    f"Unable to read session child at index {index} for "
                    f"connection {connection_id!r}"
                ) from e

            candidate = self._require_dispatch(
                candidate,
                source=f"GuiConnection.Children({index})",
            )

            candidate_id = self._get_string_property(
                candidate,
                "Id",
                source=f"GuiConnection.Children({index})",
            )

            if candidate_id == session_id:
                candidate_type = self._get_optional_string_property(
                    candidate,
                    "Type",
                )

                if (
                    candidate_type is not None
                    and candidate_type != "GuiSession"
                ):
                    raise SapComError(
                        f"Object {session_id!r} was expected to be a "
                        f"GuiSession but reported type {candidate_type!r}"
                    )

                return candidate

        raise SapSessionNotFoundError(
            f"SAP GUI session not found: connection={connection_id!r}, "
            f"session={session_id!r}"
        )

    def find_component(
        self,
        connection_id: str,
        session_id: str,
        component_id: str,
        *,
        raise_on_missing: bool = True,
    ) -> DispatchLike | None:
        """
        Resolve a component relative to a session.

        SAP GUI component IDs are normally session-relative, such as:

            wnd[0]/usr/ctxtDY_PATH

        Depending on the SAP GUI API version, ``FindById`` may either return
        ``None`` or raise a COM exception when the object is missing.
        """
        self._validate_id(connection_id, name="connection_id")
        self._validate_id(session_id, name="session_id")
        self._validate_id(component_id, name="component_id")

        session = self.get_session(connection_id, session_id)

        try:
            # False tells SAP GUI not to raise for a missing component.
            result = session.FindById(component_id, False)
        except TypeError:
            # Compatibility fallback for an unusual dispatch wrapper that
            # exposes only the one-argument form.
            try:
                result = session.FindById(component_id)
            except Exception as e:
                if not raise_on_missing:
                    return None

                raise SapComponentNotFoundError(
                    self._component_missing_message(
                        connection_id,
                        session_id,
                        component_id,
                    )
                ) from e
        except Exception as e:
            if not raise_on_missing:
                self._logger.debug(
                    "SAP FindById failed for component %r",
                    component_id,
                    exc_info=True,
                )
                return None

            raise SapComError(
                f"SAP FindById failed: connection={connection_id!r}, "
                f"session={session_id!r}, component={component_id!r}"
            ) from e

        if result is None:
            if raise_on_missing:
                raise SapComponentNotFoundError(
                    self._component_missing_message(
                        connection_id,
                        session_id,
                        component_id,
                    )
                )
            return None

        return self._require_dispatch(
            result,
            source=f"GuiSession.FindById({component_id!r})",
        )

    def component_exists(
        self,
        connection_id: str,
        session_id: str,
        component_id: str,
    ) -> bool:
        return (
            self.find_component(
                connection_id,
                session_id,
                component_id,
                raise_on_missing=False,
            )
            is not None
        )

    @staticmethod
    def get_property(
        dispatch: DispatchLike,
        prop: str,
        /,
    ) -> Any:
        """
        Read a dynamic COM property with contextual error handling.
        """
        if not prop:
            raise ValueError("property_name must not be empty")

        try:
            return getattr(dispatch, prop)
        except Exception as e:
            raise SapComError(
                f"Unable to read COM property {prop!r}"
            ) from e

    @staticmethod
    def _validate_id(value: str, *, name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")

    @staticmethod
    def _component_missing_message(
        connection_id: str,
        session_id: str,
        component_id: str,
    ) -> str:
        return (
            f"SAP GUI component not found: connection={connection_id!r}, "
            f"session={session_id!r}, component={component_id!r}"
        )

    @staticmethod
    def _require_dispatch(
        value: object,
        *,
        source: str,
        expected_type: str | None = None,
    ) -> DispatchLike:
        """
        Validate a late-bound COM object without requiring one concrete
        win32com dispatch implementation.

        ``win32com`` may produce dynamic dispatch objects or generated wrapper
        classes, so strict ``isinstance(value, CDispatch)`` checks are brittle.
        """
        if value is None:
            raise SapComError(f"{source} returned None")

        missing_members = [
            member
            for member in ("Id", "Type")
            if not hasattr(value, member)
        ]

        if missing_members:
            raise SapComError(
                f"{source} returned an incompatible object of type "
                f"{type(value)!r}; missing members={missing_members!r}"
            )

        dispatch = cast(DispatchLike, value)

        if expected_type is not None:
            try:
                actual_type = str(dispatch.Type)
            except Exception as e:
                raise SapComError(
                    f"Unable to inspect the SAP type returned by {source}"
                ) from e

            if actual_type != expected_type:
                raise SapComError(
                    f"{source} returned SAP type {actual_type!r}; "
                    f"expected {expected_type!r}"
                )

        return dispatch

    @staticmethod
    def _get_string_property(
        dispatch: DispatchLike,
        property_name: str,
        *,
        source: str,
    ) -> str:
        try:
            value = getattr(dispatch, property_name)
        except Exception as e:
            raise SapComError(
                f"Unable to read {source}.{property_name}"
            ) from e

        if value is None:
            raise SapComError(
                f"{source}.{property_name} returned None"
            )

        return str(value)

    @staticmethod
    def _get_optional_string_property(
        dispatch: DispatchLike,
        property_name: str,
    ) -> str | None:
        try:
            value = getattr(dispatch, property_name)
        except Exception:
            return None

        return None if value is None else str(value)


def get_application_com():
    try:
        launch_executable(AppManager.exe())
        sap_gui = win32.GetObject(SAPGUI_OBJECT_ID)
        if (not isinstance(sap_gui, win32.CDispatch)):
            raise RuntimeError(LogMsg(
                f"sap_gui = win32.GetObject('{SAPGUI_OBJECT_ID}') is not CDispatch",
                sap_gui=annotate(sap_gui)
            ))
        app = sap_gui.GetScriptingEngine
        if not isinstance(app, win32.CDispatch):
            raise RuntimeError(LogMsg(
                f"app = win32.GetObject('{SAPGUI_OBJECT_ID}').GetScriptingEngine is not CDispatch",
                app=annotate(app)
            ))
        return app
    except Exception as e:
        raise RuntimeError(LogMsg.err(e)) from e
