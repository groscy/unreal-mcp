"""Unit tests for UEConnection error paths — no live UE required."""

from unittest.mock import MagicMock, patch

import pytest

from unreal_mcp.connection import ConnectionState, UEConnection, _parse_result


class TestParseResult:
    def test_success_with_stdout(self):
        raw = {
            "success": True,
            "output": [{"type": "stdout", "output": "hello\n"}],
        }
        r = _parse_result(raw)
        assert r["ok"] is True
        assert r["stdout"] == "hello"  # trailing newline stripped
        assert r["error"] is None

    def test_failure_with_error(self):
        raw = {
            "success": False,
            "output": [{"type": "error", "output": "NameError: name 'x' is not defined"}],
        }
        r = _parse_result(raw)
        assert r["ok"] is False
        assert r["error"] == "NameError: name 'x' is not defined"

    def test_json_result_parsed(self):
        # result field is top-level (not in output list)
        raw = {
            "success": True,
            "result": '{"key": 42}',
            "output": [{"type": "stdout", "output": ""}],
        }
        r = _parse_result(raw)
        assert r["result"] == {"key": 42}

    def test_non_json_result_kept_as_string(self):
        raw = {
            "success": True,
            "result": "some_value",
            "output": [{"type": "stdout", "output": ""}],
        }
        r = _parse_result(raw)
        assert r["result"] == "some_value"


class TestUEConnectionNoUE:
    def test_ping_when_not_connected(self):
        conn = UEConnection()
        result = conn.ping()
        assert result["ok"] is False
        assert result["connected"] is False
        assert result["state"] == "disconnected"

    def test_execute_when_not_connected(self):
        conn = UEConnection()
        result = conn.execute("print('hello')")
        assert result["ok"] is False
        assert "not connected" in result["error"].lower()

    def test_connect_timeout_returns_false(self):
        conn = UEConnection()
        with patch("unreal_mcp.connection.RemoteExecution") as MockRE, \
             patch("unreal_mcp.connection._CONNECT_MODE", "discovery"):
            instance = MockRE.return_value
            instance.remote_nodes = []  # no nodes found
            with patch("unreal_mcp.connection._CONNECT_TIMEOUT", 0.01):
                result = conn.connect()
        assert result is False
        assert conn.state == ConnectionState.DISCONNECTED

    def test_connect_exception_returns_false(self):
        conn = UEConnection()
        with patch("unreal_mcp.connection.RemoteExecution") as MockRE, \
             patch("unreal_mcp.connection._CONNECT_MODE", "discovery"):
            instance = MockRE.return_value
            instance.start.side_effect = OSError("socket error")
            result = conn.connect()
        assert result is False
        assert conn.state == ConnectionState.DISCONNECTED

    def test_connection_error_flags_reconnecting(self):
        """execute() no longer reconnects inline; it flags state for the background task."""
        conn = UEConnection()
        conn.state = ConnectionState.CONNECTED
        conn._re = MagicMock()
        conn._re.run_command.side_effect = ConnectionError("dropped")

        result = conn.execute("1+1")
        assert result["ok"] is False
        assert conn.state == ConnectionState.RECONNECTING

    def test_disconnect_clears_state(self):
        conn = UEConnection()
        conn._re = MagicMock()
        conn.state = ConnectionState.CONNECTED
        conn.disconnect()
        assert conn.state == ConnectionState.DISCONNECTED
        assert conn._re is None
