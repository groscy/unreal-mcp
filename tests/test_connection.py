"""Unit tests for UEConnection error paths — no live UE required."""

from unittest.mock import MagicMock, patch

import pytest

from unreal_mcp.connection import UEConnection, _parse_result


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

    def test_execute_when_not_connected(self):
        conn = UEConnection()
        result = conn.execute("print('hello')")
        assert result["ok"] is False
        assert "not connected" in result["error"].lower()

    def test_connect_timeout_returns_false(self):
        conn = UEConnection()
        with patch("unreal_mcp.connection.RemoteExecution") as MockRE:
            instance = MockRE.return_value
            instance.remote_nodes = []  # no nodes found
            with patch("unreal_mcp.connection._CONNECT_TIMEOUT", 0.01):
                result = conn.connect()
        assert result is False
        assert conn.is_connected is False

    def test_connect_exception_returns_false(self):
        conn = UEConnection()
        with patch("unreal_mcp.connection.RemoteExecution") as MockRE:
            instance = MockRE.return_value
            instance.start.side_effect = OSError("socket error")
            result = conn.connect()
        assert result is False
        assert conn.is_connected is False

    def test_reconnect_on_connection_error(self):
        conn = UEConnection()
        conn.is_connected = True
        conn._re = MagicMock()
        conn._re.run_command.side_effect = ConnectionError("dropped")

        with patch.object(conn, "reconnect", return_value=False) as mock_reconnect:
            result = conn.execute("1+1")
        assert result["ok"] is False
        mock_reconnect.assert_called_once()

    def test_disconnect_clears_state(self):
        conn = UEConnection()
        conn._re = MagicMock()
        conn.is_connected = True
        conn.disconnect()
        assert conn.is_connected is False
        assert conn._re is None
