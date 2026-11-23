from types import SimpleNamespace
import unittest
from unittest.mock import Mock, PropertyMock, patch

from resin.gui.com.gateway import ComGateway
from resin.gui.context import SapContext
from resin.gui.core.connection import Connection


class GuiConnectionTests(unittest.TestCase):
    def setUp(self):
        self.gateway = Mock(spec=ComGateway)
        self.connection = Connection(
            gateway=self.gateway,
            context=SapContext(connection_id="/app/con[0]"),
            session_capacity=6,
        )

    def test_create_session_returns_new_runtime_id_not_last_child(self):
        source = SimpleNamespace(
            Id="/app/con[0]/ses[0]", Type="GuiSession", CreateSession=Mock()
        )
        created = SimpleNamespace(Id="/app/con[0]/ses[1]", Type="GuiSession")
        sessions = [source]
        children = Mock(side_effect=lambda index: sessions[index])
        children.Count = 1

        def create():
            sessions.insert(0, created)
            children.Count = len(sessions)

        source.CreateSession.side_effect = create
        self.gateway.get_connection.return_value = SimpleNamespace(
            Id=self.connection.id, Children=children
        )
        self.gateway.get_session.return_value = source

        result = self.connection.create_session(timeout=1.0, poll_interval=0.01)

        self.assertEqual(result.id, created.Id)
        self.assertEqual(result.connection_id, self.connection.id)
        source.CreateSession.assert_called_once_with()

    def test_create_session_rejects_invalid_polling_before_creation(self):
        dispatch = Mock()
        dispatch.Children.Count = 1
        self.gateway.get_connection.return_value = dispatch

        with self.assertRaises(ValueError):
            self.connection.create_session(timeout=0)

        self.gateway.get_session.assert_not_called()

    def test_wait_for_session_capacity_polls_until_space_is_available(self):
        with (
            patch.object(
                Connection, "session_count", new_callable=PropertyMock,
                side_effect=[6, 5],
            ),
            patch("resin.gui.core.connection.runtime.pump_waiting_messages") as pump,
            patch("resin.gui.core.connection.time.sleep") as sleep,
        ):
            result = self.connection.wait_for_session_capacity(
                timeout=1.0, poll_interval=0.01
            )

        self.assertIs(result, self.connection)
        pump.assert_called_once_with()
        sleep.assert_called_once()

    def test_wait_for_session_capacity_times_out_when_full(self):
        with (
            patch.object(
                Connection, "session_count", new_callable=PropertyMock,
                return_value=6,
            ),
            patch("resin.gui.core.connection.time.monotonic", side_effect=[0, 1]),
            patch("resin.gui.core.connection.runtime.pump_waiting_messages") as pump,
        ):
            with self.assertRaises(TimeoutError):
                self.connection.wait_for_session_capacity(timeout=0.5)

        pump.assert_not_called()


if __name__ == "__main__":
    unittest.main()
