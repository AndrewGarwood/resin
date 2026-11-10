"""
*`@file`* `gui/services/pool/utils`
"""
import time
from resin.utils import runtime
from resin.gui.core.application import Application
from .session_locator import (SessionLocator)
from .session_binding import (SessionBinding)
from pyqi import Array, require, export, fs
from resin.gui.config import (AppManager)

def discover_session_locators() -> list[SessionLocator]:
    with runtime.com_apartment():
        app = Application.attach()
        app_id = app.id
        locs: list[SessionLocator] = []
        for c in app.connections:
            conn_id = c.id
            locs.extend(Array.map(
                c.sessions, 
                lambda s: SessionLocator(
                    connection_id=conn_id,
                    session_id=s.id,
                    application_id=app_id
                )
            ))
        return locs

def discover_session_bindings() -> list[SessionBinding]:
    return Array.map(
        discover_session_locators(), 
        lambda loc: SessionBinding(loc, close_on_exit=False)
    )

def provision_session_bindings(
    count: int,
    /,
    *,
    connection_index: int = 0,
    close_created_sessions_on_exit: bool = True,
) -> list[SessionBinding]:
    count = require.positive_integer(
        count,
        "provision session count",
    )

    with runtime.com_apartment():
        app = Application.attach()
        app_id = app.id
        connection = app.get_connection(connection_index)
        conn_id = connection.id
        existing_sessions = list(connection.sessions)
        selected_sessions = existing_sessions[:count]
        bindings = Array.map(
            selected_sessions,
            lambda s: SessionBinding(
                locator=SessionLocator(
                    application_id=app_id, 
                    connection_id=conn_id, 
                    session_id=s.id
                ),
                close_on_exit=False # b/c already existed
            )
        )

        while len(bindings) < count:
            created_session = connection.create_session()
            bindings.append(
                SessionBinding(
                    locator=SessionLocator(
                        application_id=app.id,
                        connection_id=connection.id,
                        session_id=created_session.id,
                    ),
                    close_on_exit=close_created_sessions_on_exit, # policy for newly created sessions
                )
            )
        return bindings


def default_sap_gui_launcher() -> None:
    """ `fs.launch_executable(AppManager.exe())` """
    _ = fs.launch_executable(AppManager.exe())
    time.sleep(2)

__all__ = export(
    provision_session_bindings, 
    discover_session_bindings, 
    discover_session_locators,
    default_sap_gui_launcher
)