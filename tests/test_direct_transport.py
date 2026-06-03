"""Unit tests for the direct loopback transport and connect-mode dispatcher."""

import json
import socket
from unittest.mock import MagicMock, patch

import pytest

from unreal_mcp.connection import ConnectionState, UEConnection
from unreal_mcp.remote_execution import (
    RemoteExecution,
    RemoteExecutionConfig,
    _RemoteExecutionCommandConnection,
    _TYPE_OPEN_CONNECTION,
    _send_open_connection_unicast,
)


# ---------------------------------------------------------------------------
# 4.1 – unicast open_connection message shape
# ---------------------------------------------------------------------------

class TestSendOpenConnectionUnicast:
    def test_sends_dest_less_open_connection(self):
        """_send_open_connection_unicast sends a dest-less open_connection with the right fields."""
        config = RemoteExecutionConfig()
        node_id = "test-node-id"

        mock_sock = MagicMock()
        with patch("unreal_mcp.remote_execution._socket.socket", return_value=mock_sock):
            _send_open_connection_unicast(node_id, config, "127.0.0.1")

        mock_sock.sendto.assert_called_once()
        data, addr = mock_sock.sendto.call_args[0]
        msg = json.loads(data.decode("utf-8"))

        assert msg["type"] == _TYPE_OPEN_CONNECTION
        assert msg["source"] == node_id
        assert "dest" not in msg
        assert msg["data"]["command_ip"] == config.command_endpoint[0]
        assert msg["data"]["command_port"] == config.command_endpoint[1]
        assert addr == ("127.0.0.1", config.multicast_group_endpoint[1])
        mock_sock.close.assert_called_once()

    def test_sends_to_custom_host(self):
        config = RemoteExecutionConfig()
        mock_sock = MagicMock()
        with patch("unreal_mcp.remote_execution._socket.socket", return_value=mock_sock):
            _send_open_connection_unicast("nid", config, "192.168.1.50")
        _, addr = mock_sock.sendto.call_args[0]
        assert addr[0] == "192.168.1.50"


# ---------------------------------------------------------------------------
# 4.2 – open_command_connection_direct success / budget exhausted
# ---------------------------------------------------------------------------

class TestOpenCommandConnectionDirect:
    def _make_re_with_mock_listen(self, accept_return=None, accept_side_effect=None):
        config = RemoteExecutionConfig()
        re = RemoteExecution(config)

        mock_channel = MagicMock()

        def fake_init(self):
            self._command_listen_socket = MagicMock()
            if accept_side_effect is not None:
                self._command_listen_socket.accept.side_effect = accept_side_effect
            else:
                self._command_listen_socket.accept.return_value = (mock_channel, ("127.0.0.1", 12345))

        return re, fake_init, mock_channel

    def test_success_when_editor_connects_back(self):
        re, fake_init, mock_channel = self._make_re_with_mock_listen()
        with patch.object(_RemoteExecutionCommandConnection, "_init_command_listen_socket", fake_init), \
             patch("unreal_mcp.remote_execution._send_open_connection_unicast"):
            re.open_command_connection_direct("127.0.0.1")
        assert re.has_command_connection()

    def test_budget_exhausted_raises_and_leaves_no_connection(self):
        re, fake_init, _ = self._make_re_with_mock_listen(accept_side_effect=socket.timeout)
        with patch.object(_RemoteExecutionCommandConnection, "_init_command_listen_socket", fake_init), \
             patch("unreal_mcp.remote_execution._send_open_connection_unicast"):
            with pytest.raises(RuntimeError, match="Remote party failed"):
                re.open_command_connection_direct("127.0.0.1")
        assert not re.has_command_connection()

    def test_applies_recv_timeout_on_success(self):
        config = RemoteExecutionConfig()
        config.command_recv_timeout = 15.0
        re = RemoteExecution(config)
        mock_channel = MagicMock()

        def fake_init(self):
            self._command_listen_socket = MagicMock()
            self._command_listen_socket.accept.return_value = (mock_channel, ("127.0.0.1", 1234))

        with patch.object(_RemoteExecutionCommandConnection, "_init_command_listen_socket", fake_init), \
             patch("unreal_mcp.remote_execution._send_open_connection_unicast"):
            re.open_command_connection_direct("127.0.0.1")

        mock_channel.settimeout.assert_called_once_with(15.0)

    def test_fallback_host_from_bind_address(self):
        """When host is omitted and bind is 0.0.0.0, direct defaults to 127.0.0.1."""
        config = RemoteExecutionConfig()
        config.multicast_bind_address = "0.0.0.0"
        re = RemoteExecution(config)
        mock_channel = MagicMock()

        def fake_init(self):
            self._command_listen_socket = MagicMock()
            self._command_listen_socket.accept.return_value = (mock_channel, ("127.0.0.1", 1234))

        sent_to = []

        def fake_send(node_id, cfg, host):
            sent_to.append(host)

        with patch.object(_RemoteExecutionCommandConnection, "_init_command_listen_socket", fake_init), \
             patch("unreal_mcp.remote_execution._send_open_connection_unicast", side_effect=fake_send):
            re.open_command_connection_direct()

        assert sent_to[0] == "127.0.0.1"


# ---------------------------------------------------------------------------
# 4.3 – mode dispatcher: auto / direct / discovery
# ---------------------------------------------------------------------------

class TestConnectModeDispatcher:
    def test_auto_falls_back_to_discovery_when_direct_fails(self):
        conn = UEConnection()
        with patch.object(conn, "connect_direct", return_value=False) as mock_direct, \
             patch.object(conn, "_connect_discovery", return_value=True) as mock_disc, \
             patch("unreal_mcp.connection._CONNECT_MODE", "auto"):
            result = conn.connect()
        assert result is True
        mock_direct.assert_called_once()
        mock_disc.assert_called_once()

    def test_auto_succeeds_on_direct_without_calling_discovery(self):
        conn = UEConnection()
        with patch.object(conn, "connect_direct", return_value=True) as mock_direct, \
             patch.object(conn, "_connect_discovery", return_value=True) as mock_disc, \
             patch("unreal_mcp.connection._CONNECT_MODE", "auto"):
            result = conn.connect()
        assert result is True
        mock_direct.assert_called_once()
        mock_disc.assert_not_called()

    def test_direct_mode_uses_only_direct(self):
        conn = UEConnection()
        with patch.object(conn, "connect_direct", return_value=True) as mock_direct, \
             patch.object(conn, "_connect_discovery") as mock_disc, \
             patch("unreal_mcp.connection._CONNECT_MODE", "direct"):
            result = conn.connect()
        assert result is True
        mock_direct.assert_called_once()
        mock_disc.assert_not_called()

    def test_discovery_mode_uses_only_discovery(self):
        conn = UEConnection()
        with patch.object(conn, "connect_direct") as mock_direct, \
             patch.object(conn, "_connect_discovery", return_value=True) as mock_disc, \
             patch("unreal_mcp.connection._CONNECT_MODE", "discovery"):
            result = conn.connect()
        assert result is True
        mock_direct.assert_not_called()
        mock_disc.assert_called_once()


# ---------------------------------------------------------------------------
# 4.4 – socket.timeout on command socket → RECONNECTING
# ---------------------------------------------------------------------------

class TestCommandSocketTimeout:
    def test_socket_timeout_flags_reconnecting(self):
        """A socket.timeout (an OSError) from run_command causes RECONNECTING, not a hang."""
        conn = UEConnection()
        conn.state = ConnectionState.CONNECTED
        conn._re = MagicMock()
        conn._re.run_command.side_effect = socket.timeout("timed out")

        result = conn.execute("print('hello')")

        assert result["ok"] is False
        assert conn.state == ConnectionState.RECONNECTING
        assert "not connected" in result["error"].lower()

    def test_successful_command_stays_connected(self):
        """A command that completes within the timeout leaves state as CONNECTED."""
        conn = UEConnection()
        conn.state = ConnectionState.CONNECTED
        conn._re = MagicMock()
        conn._re.run_command.return_value = {
            "success": True,
            "result": "None",
            "output": [{"type": "stdout", "output": "ok\n"}],
        }

        result = conn.execute("print('ok')")

        assert result["ok"] is True
        assert conn.state == ConnectionState.CONNECTED
